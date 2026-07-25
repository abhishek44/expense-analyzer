"""ML prediction router for automatic transaction categorization."""

import logging
import subprocess
import sys
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Transaction, Category, ReviewStatus, CategorisedBy

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ml", tags=["ML Predictions"])


class PredictRequest(BaseModel):
    details: str
    notes: Optional[str] = ""
    debit: Optional[float] = None
    credit: Optional[float] = None
    account_name: Optional[str] = ""
    account_type: Optional[str] = ""


class BatchPredictRequest(BaseModel):
    transaction_ids: Optional[list[int]] = None


@router.post("/predict", summary="Predict category for a transaction")
async def predict_category_endpoint(req: PredictRequest):
    from ml_model import predict_category as ml_predict

    result = ml_predict(
        details=req.details,
        notes=req.notes or "",
        debit=req.debit,
        credit=req.credit,
        account_name=req.account_name or "",
        account_type=req.account_type or "",
    )

    if result is None:
        raise HTTPException(status_code=503, detail="Model not available. Train first using POST /api/ml/train")

    return result


@router.post("/predict-pending", summary="Predict categories for pending transactions")
async def predict_pending(req: BatchPredictRequest, db: Session = Depends(get_db)):
    from ml_model import predict_batch

    query = db.query(Transaction).filter(Transaction.review_status == ReviewStatus.PENDING.value)
    if req.transaction_ids:
        query = query.filter(Transaction.id.in_(req.transaction_ids))

    transactions = query.all()
    if not transactions:
        return {"predictions": [], "message": "No pending transactions found"}

    # Build L1 category name → id lookup
    l1_cats = {c.name: c.id for c in db.query(Category).filter(Category.level == 1).all()}

    batch_input = [{
        "details": t.raw_details or "",
        "notes": t.notes or "",
        "debit": t.debit,
        "credit": t.credit,
        "account_name": t.account_name or "",
        "account_type": t.account_type or "",
    } for t in transactions]

    results = predict_batch(batch_input)

    predictions = []
    for t, pred in zip(transactions, results):
        if pred is None:
            raise HTTPException(status_code=503, detail="Model not available. Train first.")

        # Map predicted category name to L1 ID
        l1_id = l1_cats.get(pred["category"])
        predictions.append({
            "transaction_id": t.id,
            "details": t.merchant_name or t.cleaned_details or t.raw_details,
            "predicted_l1_category": pred["category"],
            "predicted_l1_category_id": l1_id,
            **pred,
        })

    return {
        "predictions": predictions,
        "total": len(predictions),
        "high_confidence": sum(1 for p in predictions if p["confidence_level"] == "high"),
        "medium_confidence": sum(1 for p in predictions if p["confidence_level"] == "medium"),
        "low_confidence": sum(1 for p in predictions if p["confidence_level"] == "low"),
    }


def _execute_model_training():
    """Background worker to run training subprocess and reload model into memory."""
    try:
        logger.info("Starting ML model training in background...")
        result = subprocess.run(
            [sys.executable, "-m", "ml_model.train"],
            capture_output=True,
            text=True,
            cwd=str(__import__("pathlib").Path(__file__).parent.parent.parent),
        )
        if result.returncode != 0:
            logger.error(f"Training failed: {result.stderr or result.stdout}")
        else:
            logger.info("Training completed successfully. Reloading model...")
            from ml_model import reload_model
            reload_model()
    except Exception as e:
        logger.error(f"Exception during background model training: {e}", exc_info=True)


@router.post("/train", summary="Train the category prediction model")
async def train_model(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    reviewed_count = db.query(Transaction).filter(
        Transaction.review_status != ReviewStatus.PENDING.value,
        Transaction.l1_category_id.isnot(None),
    ).count()

    if reviewed_count < 20:
        raise HTTPException(status_code=400, detail=f"Need at least 20 reviewed transactions, found {reviewed_count}.")

    background_tasks.add_task(_execute_model_training)
    return {
        "success": True,
        "message": "Model training initiated in background",
        "reviewed_transactions": reviewed_count,
    }


@router.get("/status", summary="Get ML model status")
async def model_status(db: Session = Depends(get_db)):
    from ml_model import get_metadata

    metadata = get_metadata()
    reviewed_count = db.query(Transaction).filter(
        Transaction.review_status != ReviewStatus.PENDING.value,
        Transaction.l1_category_id.isnot(None),
    ).count()
    pending_count = db.query(Transaction).filter(Transaction.review_status == ReviewStatus.PENDING.value).count()

    return {
        "model_available": metadata is not None,
        "model_metadata": metadata,
        "reviewed_transactions": reviewed_count,
        "pending_transactions": pending_count,
        "can_train": reviewed_count >= 20,
    }


@router.post("/evaluate", summary="Evaluate model against reviewed transactions")
async def evaluate_model(db: Session = Depends(get_db)):
    from ml_model import predict_batch, get_metadata

    metadata = get_metadata()
    if metadata is None:
        raise HTTPException(status_code=503, detail="No trained model available.")

    # Build L1 id → name lookup
    l1_cats = {c.id: c.name for c in db.query(Category).filter(Category.level == 1).all()}

    transactions = db.query(Transaction).filter(
        Transaction.review_status != ReviewStatus.PENDING.value,
        Transaction.l1_category_id.isnot(None),
    ).all()

    if not transactions:
        raise HTTPException(status_code=400, detail="No reviewed transactions to evaluate")

    batch_input = [{
        "details": t.raw_details or "",
        "notes": t.notes or "",
        "debit": t.debit,
        "credit": t.credit,
        "account_name": t.account_name or "",
        "account_type": t.account_type or "",
    } for t in transactions]

    results = predict_batch(batch_input)

    correct = 0
    total = len(transactions)
    mismatches = []

    for t, pred in zip(transactions, results):
        if pred is None:
            continue
        actual_name = l1_cats.get(t.l1_category_id, "Unknown")
        if pred["category"] == actual_name:
            correct += 1
        else:
            mismatches.append({
                "transaction_id": t.id,
                "details": t.merchant_name or t.raw_details,
                "actual_category": actual_name,
                "predicted_category": pred["category"],
                "confidence": pred["confidence"],
            })

    accuracy = correct / total if total > 0 else 0
    mismatches.sort(key=lambda x: x["confidence"], reverse=True)

    return {
        "accuracy": round(accuracy, 4),
        "correct": correct,
        "incorrect": total - correct,
        "total_evaluated": total,
        "model_trained_on": metadata.get("num_samples"),
        "model_test_accuracy": metadata.get("test_accuracy"),
        "sample_mismatches": mismatches[:20],
    }
