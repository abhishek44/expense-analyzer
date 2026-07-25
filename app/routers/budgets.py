"""Budgets API router."""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Budget, Transaction, Category

router = APIRouter(prefix="/api/budgets", tags=["Budgets"])


class BudgetCreate(BaseModel):
    l1_category_name: str = Field(..., description="L1 category name")
    amount_limit: float = Field(..., gt=0, description="Amount limit")
    period: str = Field("MONTHLY", description="MONTHLY, WEEKLY, YEARLY")
    is_active: bool = Field(True, description="Is the budget active")
    rollover: bool = Field(False, description="Carries over to next period")


class BudgetUpdate(BaseModel):
    amount_limit: Optional[float] = Field(None, gt=0)
    period: Optional[str] = None
    is_active: Optional[bool] = None
    rollover: Optional[bool] = None


@router.post("", summary="Create a new budget")
async def create_budget(data: BudgetCreate, db: Session = Depends(get_db)) -> dict:
    # Check if a budget already exists for this L1 category
    existing = db.query(Budget).filter(Budget.l1_category_name == data.l1_category_name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Budget already exists for category {data.l1_category_name}")
        
    b = Budget(
        l1_category_name=data.l1_category_name,
        amount_limit=data.amount_limit,
        period=data.period,
        is_active=1 if data.is_active else 0,
        rollover=1 if data.rollover else 0,
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return {"success": True, "data": b.to_dict()}


@router.put("/{budget_id}", summary="Update a budget")
async def update_budget(budget_id: int, data: BudgetUpdate, db: Session = Depends(get_db)) -> dict:
    b = db.query(Budget).filter(Budget.id == budget_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Budget not found")
        
    if data.amount_limit is not None:
        b.amount_limit = data.amount_limit
    if data.period is not None:
        b.period = data.period
    if data.is_active is not None:
        b.is_active = 1 if data.is_active else 0
    if data.rollover is not None:
        b.rollover = 1 if data.rollover else 0
        
    db.commit()
    db.refresh(b)
    return {"success": True, "data": b.to_dict()}


@router.get("", summary="Get all budgets")
async def get_budgets(db: Session = Depends(get_db)) -> List[dict]:
    budgets = db.query(Budget).all()
    return [b.to_dict() for b in budgets]


@router.get("/progress", summary="Get budgets progress")
async def get_budgets_progress(
    month: Optional[str] = Query(None, description="Month in YYYY-MM format, default is current month"),
    db: Session = Depends(get_db),
) -> dict:
    # 1. Resolve month (default to current calendar month)
    if not month:
        month = datetime.now().strftime("%Y-%m")
        
    start_date = f"{month}-01"
    end_date = f"{month}-31"

    y_str, m_str = month.split("-")
    y_val = int(y_str)
    m_val = int(m_str)

    if m_val >= 4:
        yearly_start_date = f"{y_val}-04-01"
        yearly_end_date = f"{y_val + 1}-03-31"
        fy_label = f"FY {y_val}-{str(y_val+1)[2:]}"
    else:
        yearly_start_date = f"{y_val - 1}-04-01"
        yearly_end_date = f"{y_val}-03-31"
        fy_label = f"FY {y_val-1}-{str(y_val)[2:]}"

    # Fetch all active budgets
    budgets = db.query(Budget).filter(Budget.is_active == 1).all()

    # Load categories mapping (ID to name) to group by category names
    all_categories = db.query(Category).filter(Category.is_archived == 0).all()
    id_to_name = {c.id: c.name for c in all_categories}

    # Aggregate monthly debits via SQL GROUP BY
    monthly_rows = db.query(
        Transaction.l1_category_id,
        Transaction.l2_category_id,
        func.sum(func.coalesce(Transaction.debit, 0.0))
    ).filter(
        Transaction.flow_direction == "debit",
        Transaction.parsed_date >= start_date,
        Transaction.parsed_date <= end_date
    ).group_by(
        Transaction.l1_category_id,
        Transaction.l2_category_id
    ).all()

    spend_map = {}
    for l1_id, l2_id, total_amount in monthly_rows:
        l1_name = id_to_name.get(l1_id, "Uncategorized")
        l2_name = id_to_name.get(l2_id, "Other")
        amount = float(total_amount or 0.0)

        if l1_name not in spend_map:
            spend_map[l1_name] = {"total": 0.0, "l2": {}}

        spend_map[l1_name]["total"] += amount
        spend_map[l1_name]["l2"][l2_name] = spend_map[l1_name]["l2"].get(l2_name, 0.0) + amount

    # Aggregate yearly debits via SQL GROUP BY
    yearly_rows = db.query(
        Transaction.l1_category_id,
        Transaction.l2_category_id,
        func.sum(func.coalesce(Transaction.debit, 0.0))
    ).filter(
        Transaction.flow_direction == "debit",
        Transaction.parsed_date >= yearly_start_date,
        Transaction.parsed_date <= yearly_end_date
    ).group_by(
        Transaction.l1_category_id,
        Transaction.l2_category_id
    ).all()

    yearly_spend_map = {}
    for l1_id, l2_id, total_amount in yearly_rows:
        l1_name = id_to_name.get(l1_id, "Uncategorized")
        l2_name = id_to_name.get(l2_id, "Other")
        amount = float(total_amount or 0.0)

        if l1_name not in yearly_spend_map:
            yearly_spend_map[l1_name] = {"total": 0.0, "l2": {}}

        yearly_spend_map[l1_name]["total"] += amount
        yearly_spend_map[l1_name]["l2"][l2_name] = yearly_spend_map[l1_name]["l2"].get(l2_name, 0.0) + amount

    # Combine budget limits with actual spends
    progress = []
    for b in budgets:
        l1 = b.l1_category_name
        limit = b.amount_limit
        yearly_limit = limit * 12
        
        # Monthly spent calculations
        spend_data = spend_map.get(l1, {"total": 0.0, "l2": {}})
        current_spend = round(spend_data["total"], 2)
        left_to_spend = round(limit - current_spend, 2)
        percentage = round((current_spend / limit) * 100, 1) if limit > 0 else 0.0
        
        l2_breakdown = []
        for l2_name, amt in spend_data["l2"].items():
            l2_breakdown.append({"name": l2_name, "spend": round(amt, 2)})
        l2_breakdown.sort(key=lambda x: x["spend"], reverse=True)

        # Yearly spent calculations
        y_spend_data = yearly_spend_map.get(l1, {"total": 0.0, "l2": {}})
        y_current_spend = round(y_spend_data["total"], 2)
        y_left_to_spend = round(yearly_limit - y_current_spend, 2)
        y_percentage = round((y_current_spend / yearly_limit) * 100, 1) if yearly_limit > 0 else 0.0
        
        y_l2_breakdown = []
        for l2_name, amt in y_spend_data["l2"].items():
            y_l2_breakdown.append({"name": l2_name, "spend": round(amt, 2)})
        y_l2_breakdown.sort(key=lambda x: x["spend"], reverse=True)

        progress.append({
            "id": b.id,
            "l1_category_name": l1,
            "period": b.period,
            "rollover": bool(b.rollover),
            "monthly": {
                "amount_limit": limit,
                "current_spend": current_spend,
                "left_to_spend": left_to_spend,
                "percentage": percentage,
                "l2_breakdown": l2_breakdown
            },
            "yearly": {
                "amount_limit": yearly_limit,
                "current_spend": y_current_spend,
                "left_to_spend": y_left_to_spend,
                "percentage": y_percentage,
                "l2_breakdown": y_l2_breakdown
            }
        })

    # Sort progress list by monthly percentage spent (highest first)
    progress.sort(key=lambda x: x["monthly"]["percentage"], reverse=True)

    return {
        "month": month,
        "fy_label": fy_label,
        "progress": progress
    }
