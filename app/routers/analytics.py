"""Analytics API router — uses parsed_date and new schema columns."""

from datetime import datetime
from typing import Optional
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Transaction, Category

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/spending-overview", summary="Monthly spending overview")
async def spending_overview(
    year: Optional[int] = None,
    db: Session = Depends(get_db),
) -> dict:
    """Monthly debit/credit totals using parsed_date."""
    query = db.query(
        Transaction.parsed_date,
        Transaction.debit,
        Transaction.credit,
    ).filter(Transaction.parsed_date.isnot(None))

    if year:
        query = query.filter(Transaction.parsed_date.like(f"{year}-%"))

    transactions = query.all()

    monthly = defaultdict(lambda: {"total_debit": 0, "total_credit": 0})
    daily = defaultdict(float)

    for t in transactions:
        month_key = t.parsed_date[:7]  # YYYY-MM
        debit = t.debit or 0
        credit = t.credit or 0
        monthly[month_key]["total_debit"] += debit
        monthly[month_key]["total_credit"] += credit
        daily[t.parsed_date] += debit

    monthly_list = sorted(
        [{"month": k, "total_debit": round(v["total_debit"], 2), "total_credit": round(v["total_credit"], 2),
          "net": round(v["total_credit"] - v["total_debit"], 2)} for k, v in monthly.items()],
        key=lambda x: x["month"],
    )

    daily_list = sorted(
        [{"date": k, "amount": round(v, 2)} for k, v in daily.items()],
        key=lambda x: x["date"],
    )

    total_debit = sum(m["total_debit"] for m in monthly_list)
    total_credit = sum(m["total_credit"] for m in monthly_list)

    return {
        "total_debit": round(total_debit, 2),
        "total_credit": round(total_credit, 2),
        "net": round(total_credit - total_debit, 2),
        "monthly": monthly_list,
        "daily": daily_list,
    }


@router.get("/category-breakdown", summary="Category spending breakdown")
async def category_breakdown(
    months: int = Query(6, ge=1, le=24),
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    db: Session = Depends(get_db),
) -> dict:
    """Per-L1-category spending totals."""
    query = db.query(Transaction).filter(
        Transaction.debit.isnot(None),
        Transaction.debit > 0,
        Transaction.parsed_date.isnot(None),
    )

    if year and month:
        prefix = f"{year}-{month:02d}"
        query = query.filter(Transaction.parsed_date.like(f"{prefix}%"))
        period_label = f"{datetime(year, month, 1).strftime('%b')} {year}"
    elif year:
        query = query.filter(Transaction.parsed_date.like(f"{year}-%"))
        period_label = str(year)
    else:
        now = datetime.now()
        cutoff_month = now.month - months
        cutoff_year = now.year
        while cutoff_month <= 0:
            cutoff_month += 12
            cutoff_year -= 1
        cutoff_date = f"{cutoff_year}-{cutoff_month:02d}-01"
        query = query.filter(Transaction.parsed_date >= cutoff_date)
        period_label = f"Last {months} months"

    transactions = query.all()

    # Build L1 category name lookup
    l1_cats = {c.id: c.name for c in db.query(Category).filter(Category.level == 1).all()}

    category_totals = defaultdict(float)
    monthly_categories = defaultdict(lambda: defaultdict(float))
    grand_total = 0

    for t in transactions:
        cat_name = l1_cats.get(t.l1_category_id, "Uncategorized")
        amount = t.debit or 0
        category_totals[cat_name] += amount
        grand_total += amount
        month_key = t.parsed_date[:7]
        monthly_categories[month_key][cat_name] += amount

    categories_list = sorted(
        [{"name": k, "total": round(v, 2),
          "percentage": round((v / grand_total * 100) if grand_total > 0 else 0, 1)}
         for k, v in category_totals.items()],
        key=lambda x: x["total"],
        reverse=True,
    )

    monthly_list = sorted(
        [{"month": m, "categories": [{"name": cat, "total": round(amt, 2)}
          for cat, amt in sorted(cats.items(), key=lambda x: x[1], reverse=True)]}
         for m, cats in monthly_categories.items()],
        key=lambda x: x["month"],
    )

    # Available years
    all_dates = db.query(Transaction.parsed_date).filter(Transaction.parsed_date.isnot(None)).distinct().all()
    all_years = sorted(set(d[0][:4] for d in all_dates if d[0]), reverse=True)

    return {
        "grand_total": round(grand_total, 2),
        "categories": categories_list,
        "monthly": monthly_list,
        "period_label": period_label,
        "available_years": [int(y) for y in all_years],
    }


@router.get("/category-transactions", summary="Transactions for a category")
async def category_transactions(
    category: str = Query(..., description="L1 category name"),
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    db: Session = Depends(get_db),
) -> dict:
    """Get all transactions for a given L1 category name."""
    # Find category ID by name
    cat = db.query(Category).filter(Category.name == category, Category.level == 1).first()

    query = db.query(Transaction).filter(
        Transaction.debit.isnot(None),
        Transaction.debit > 0,
    )

    if category == "Uncategorized":
        query = query.filter(Transaction.l1_category_id.is_(None))
    elif cat:
        query = query.filter(Transaction.l1_category_id == cat.id)
    else:
        return {"category": category, "count": 0, "total": 0, "transactions": []}

    if year:
        query = query.filter(Transaction.parsed_date.like(f"{year}-%"))
    if month and year:
        query = query.filter(Transaction.parsed_date.like(f"{year}-{month:02d}%"))

    txns = query.order_by(Transaction.parsed_date.desc()).all()

    result = [{
        "id": t.id,
        "date": t.parsed_date or t.raw_date,
        "details": (t.merchant_name or t.cleaned_details or t.raw_details or "")[:120],
        "debit": t.debit or 0,
        "account": t.account_name,
        "notes": t.notes,
    } for t in txns]

    return {
        "category": category,
        "count": len(result),
        "total": round(sum(t["debit"] for t in result), 2),
        "transactions": result,
    }


@router.get("/account-analysis", summary="Account-level analysis")
async def account_analysis(db: Session = Depends(get_db)) -> dict:
    transactions = db.query(
        Transaction.parsed_date,
        Transaction.debit,
        Transaction.credit,
        Transaction.account_name,
        Transaction.account_type,
    ).all()

    by_account = defaultdict(lambda: {"total_debit": 0, "total_credit": 0, "count": 0})
    by_type = defaultdict(lambda: {"total_debit": 0, "total_credit": 0, "count": 0})
    monthly_accounts = defaultdict(lambda: defaultdict(lambda: {"debit": 0, "credit": 0}))

    for t in transactions:
        acc = t.account_name or "Unknown"
        acc_type = t.account_type or "Unknown"
        debit = t.debit or 0
        credit = t.credit or 0

        by_account[acc]["total_debit"] += debit
        by_account[acc]["total_credit"] += credit
        by_account[acc]["count"] += 1

        by_type[acc_type]["total_debit"] += debit
        by_type[acc_type]["total_credit"] += credit
        by_type[acc_type]["count"] += 1

        if t.parsed_date:
            month_key = t.parsed_date[:7]
            monthly_accounts[month_key][acc]["debit"] += debit
            monthly_accounts[month_key][acc]["credit"] += credit

    account_list = sorted(
        [{"name": k, "total_debit": round(v["total_debit"], 2), "total_credit": round(v["total_credit"], 2), "count": v["count"]}
         for k, v in by_account.items()],
        key=lambda x: x["total_debit"], reverse=True,
    )
    type_list = sorted(
        [{"type": k, "total_debit": round(v["total_debit"], 2), "total_credit": round(v["total_credit"], 2), "count": v["count"]}
         for k, v in by_type.items()],
        key=lambda x: x["total_debit"], reverse=True,
    )
    monthly_list = sorted(
        [{"month": month, "accounts": [{"name": acc, "debit": round(vals["debit"], 2), "credit": round(vals["credit"], 2)}
          for acc, vals in accs.items()]} for month, accs in monthly_accounts.items()],
        key=lambda x: x["month"],
    )

    return {"by_account": account_list, "by_type": type_list, "monthly": monthly_list}


@router.get("/top-transactions", summary="Top merchants and largest transactions")
async def top_transactions(limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)) -> dict:
    transactions = db.query(Transaction).all()

    merchant_stats = defaultdict(lambda: {"count": 0, "total": 0})
    all_txns = []

    for t in transactions:
        display = t.merchant_name or t.cleaned_details or t.raw_details or "Unknown"
        debit = t.debit or 0
        credit = t.credit or 0

        if debit > 0:
            merchant_stats[display]["count"] += 1
            merchant_stats[display]["total"] += debit

        l1_name = t.l1_category.name if t.l1_category else None
        all_txns.append({
            "id": t.id,
            "date": t.parsed_date or t.raw_date,
            "details": display[:100],
            "debit": debit,
            "credit": credit,
            "account": t.account_name,
            "category": l1_name,
        })

    top_merchants = sorted(
        [{"name": k, "count": v["count"], "total": round(v["total"], 2)} for k, v in merchant_stats.items() if v["count"] > 0],
        key=lambda x: x["total"], reverse=True,
    )[:limit]

    largest_debits = sorted([t for t in all_txns if t["debit"] > 0], key=lambda x: x["debit"], reverse=True)[:limit]
    largest_credits = sorted([t for t in all_txns if t["credit"] > 0], key=lambda x: x["credit"], reverse=True)[:limit]

    recurring = sorted(
        [{"name": k, "count": v["count"], "total": round(v["total"], 2), "avg": round(v["total"] / v["count"], 2)}
         for k, v in merchant_stats.items() if v["count"] >= 3],
        key=lambda x: x["count"], reverse=True,
    )[:limit]

    return {"top_merchants": top_merchants, "largest_debits": largest_debits, "largest_credits": largest_credits, "recurring": recurring}
