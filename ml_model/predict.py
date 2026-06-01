"""
Prediction service for transaction category classification.

Returns L1 category predictions with confidence scores.
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ml_model.preprocessing import build_enhanced_text

MODEL_DIR = Path(__file__).parent
MODEL_PATH = MODEL_DIR / "category_model.joblib"
METADATA_PATH = MODEL_DIR / "model_metadata.json"

CONFIDENCE_HIGH = 0.6
CONFIDENCE_LOW = 0.3

_model = None
_metadata = None


def _get_amount_bucket(amount: float) -> str:
    amount = abs(amount)
    if amount <= 50:
        return "tiny"
    elif amount <= 200:
        return "small"
    elif amount <= 500:
        return "medium"
    elif amount <= 2000:
        return "large"
    elif amount <= 10000:
        return "xlarge"
    else:
        return "huge"


def get_model():
    global _model
    if _model is None:
        if not MODEL_PATH.exists():
            return None
        _model = joblib.load(MODEL_PATH)
    return _model


def get_metadata() -> dict | None:
    global _metadata
    if _metadata is None:
        if not METADATA_PATH.exists():
            return None
        with open(METADATA_PATH) as f:
            _metadata = json.load(f)
    return _metadata


def reload_model():
    global _model, _metadata
    _model = None
    _metadata = None
    return get_model()


def predict_category(
    details: str,
    notes: str = "",
    debit: float | None = None,
    credit: float | None = None,
    account_name: str = "",
    account_type: str = "",
) -> dict | None:
    """
    Predict L1 category for a single transaction.

    Returns dict with:
        - category: predicted L1 category name
        - confidence: probability score (0-1)
        - confidence_level: "high", "medium", or "low"
        - top_predictions: list of top 3 (category, probability) pairs
    """
    model = get_model()
    if model is None:
        return None

    text = build_enhanced_text(details, notes)
    amount = debit if debit is not None else (credit or 0)
    log_amount = np.log1p(abs(amount))
    is_debit = 1 if debit is not None else 0
    amount_bucket = _get_amount_bucket(amount)
    flow_direction = "debit" if debit is not None else "credit"
    day_of_week = "-1"  # unknown for ad-hoc predictions

    X = pd.DataFrame([{
        "text": text,
        "Account_name": account_name or "unknown",
        "Account_type": account_type or "unknown",
        "amount_bucket": amount_bucket,
        "flow_direction": flow_direction,
        "day_of_week": day_of_week,
        "log_amount": log_amount,
        "is_debit": is_debit,
    }])

    probabilities = model.predict_proba(X)[0]
    classes = model.classes_

    top_indices = np.argsort(probabilities)[::-1][:3]
    top_predictions = [
        {"category": classes[i], "probability": round(float(probabilities[i]), 4)}
        for i in top_indices
    ]

    best_idx = top_indices[0]
    confidence = float(probabilities[best_idx])
    predicted_category = classes[best_idx]

    if confidence >= CONFIDENCE_HIGH:
        confidence_level = "high"
    elif confidence >= CONFIDENCE_LOW:
        confidence_level = "medium"
    else:
        confidence_level = "low"

    return {
        "category": predicted_category,
        "confidence": round(confidence, 4),
        "confidence_level": confidence_level,
        "top_predictions": top_predictions,
    }


def predict_batch(transactions: list[dict]) -> list[dict | None]:
    """
    Predict L1 categories for multiple transactions.

    Args:
        transactions: list of dicts with keys:
            details, notes, debit, credit, account_name, account_type
    """
    model = get_model()
    if model is None:
        return [None] * len(transactions)

    rows = []
    for t in transactions:
        text = build_enhanced_text(t.get("details", ""), t.get("notes", ""))
        debit = t.get("debit")
        credit = t.get("credit")
        amount = debit if debit is not None else (credit or 0)
        rows.append({
            "text": text,
            "Account_name": t.get("account_name") or "unknown",
            "Account_type": t.get("account_type") or "unknown",
            "amount_bucket": _get_amount_bucket(amount),
            "flow_direction": "debit" if debit is not None else "credit",
            "day_of_week": "-1",
            "log_amount": np.log1p(abs(amount)),
            "is_debit": 1 if debit is not None else 0,
        })

    X = pd.DataFrame(rows)
    probabilities = model.predict_proba(X)
    classes = model.classes_

    results = []
    for probs in probabilities:
        top_indices = np.argsort(probs)[::-1][:3]
        top_predictions = [
            {"category": classes[i], "probability": round(float(probs[i]), 4)}
            for i in top_indices
        ]
        best_idx = top_indices[0]
        confidence = float(probs[best_idx])

        if confidence >= CONFIDENCE_HIGH:
            confidence_level = "high"
        elif confidence >= CONFIDENCE_LOW:
            confidence_level = "medium"
        else:
            confidence_level = "low"

        results.append({
            "category": classes[best_idx],
            "confidence": round(confidence, 4),
            "confidence_level": confidence_level,
            "top_predictions": top_predictions,
        })

    return results
