"""Analytics API router with aggregation endpoints for dashboard charts."""

from datetime import datetime
from typing import Optional
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, extract

from app.database import get_db
from app.models import Transaction

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string in multiple formats."""
    if not date_str:
        return None
    for fmt in ["%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"]:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


@router.get("/spending-overview", summary="Monthly spending overview")
async def spending_overview(
    year: Optional[int] = None,
    db: Session = Depends(get_db),
) -> dict:
    """Monthly debit/credit totals and daily amounts for heatmap."""
    transactions = db.query(
        Transaction.Date,
        Transaction.Debit,
        Transaction.Credit,
    ).all()

    monthly = defaultdict(lambda: {"total_debit": 0, "total_credit": 0})
    daily = defaultdict(float)

    for t in transactions:
        dt = parse_date(t.Date)
        if not dt:
            continue
        if year and dt.year != year:
            continue

        month_key = dt.strftime("%Y-%m")
        debit = t.Debit or 0
        credit = t.Credit or 0
        monthly[month_key]["total_debit"] += debit
        monthly[month_key]["total_credit"] += credit

        day_key = dt.strftime("%Y-%m-%d")
        daily[day_key] += debit  # heatmap shows spending (debits)

    monthly_list = sorted(
        [
            {
                "month": k,
                "total_debit": round(v["total_debit"], 2),
                "total_credit": round(v["total_credit"], 2),
                "net": round(v["total_credit"] - v["total_debit"], 2),
            }
            for k, v in monthly.items()
        ],
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
    months: int = Query(6, ge=1, le=24, description="Months back to include"),
    year: Optional[int] = Query(None, description="Filter to specific year"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Filter to specific month (requires year)"),
    db: Session = Depends(get_db),
) -> dict:
    """Per-category spend totals and monthly trends.

    Supports three modes:
    - year + month: Show data for a single month
    - year only: Show data for the whole year
    - neither: Show last N months (default 6)
    """
    transactions = db.query(
        Transaction.Date,
        Transaction.Debit,
        Transaction.Category,
    ).filter(Transaction.Debit.isnot(None), Transaction.Debit > 0).all()

    # Determine filter mode
    use_specific_period = year is not None

    now = datetime.now()
    if not use_specific_period:
        cutoff_month = now.month - months
        cutoff_year = now.year
        while cutoff_month <= 0:
            cutoff_month += 12
            cutoff_year -= 1

    category_totals = defaultdict(float)
    monthly_categories = defaultdict(lambda: defaultdict(float))
    grand_total = 0
    period_label = ""

    for t in transactions:
        dt = parse_date(t.Date)
        if not dt:
            continue

        # Apply filtering
        if use_specific_period:
            if dt.year != year:
                continue
            if month is not None and dt.month != month:
                continue
        else:
            if (dt.year, dt.month) < (cutoff_year, cutoff_month):
                continue

        cat = t.Category or "Uncategorized"
        amount = t.Debit or 0
        category_totals[cat] += amount
        grand_total += amount

        month_key = dt.strftime("%Y-%m")
        monthly_categories[month_key][cat] += amount

    # Build period label
    if use_specific_period:
        if month is not None:
            month_names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
            period_label = f"{month_names[month - 1]} {year}"
        else:
            period_label = str(year)
    else:
        period_label = f"Last {months} months"

    categories_list = sorted(
        [
            {
                "name": k,
                "total": round(v, 2),
                "percentage": round((v / grand_total * 100) if grand_total > 0 else 0, 1),
            }
            for k, v in category_totals.items()
        ],
        key=lambda x: x["total"],
        reverse=True,
    )

    monthly_list = sorted(
        [
            {
                "month": m,
                "categories": [
                    {"name": cat, "total": round(amt, 2)}
                    for cat, amt in sorted(cats.items(), key=lambda x: x[1], reverse=True)
                ],
            }
            for m, cats in monthly_categories.items()
        ],
        key=lambda x: x["month"],
    )

    # Collect available years for the filter UI
    all_years = set()
    for t in transactions:
        dt = parse_date(t.Date)
        if dt:
            all_years.add(dt.year)

    return {
        "grand_total": round(grand_total, 2),
        "categories": categories_list,
        "monthly": monthly_list,
        "period_label": period_label,
        "available_years": sorted(all_years, reverse=True),
    }


@router.get("/category-transactions", summary="Transactions for a category")
async def category_transactions(
    category: str = Query(..., description="Category name"),
    year: Optional[int] = Query(None, description="Filter to specific year"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Filter to specific month"),
    db: Session = Depends(get_db),
) -> dict:
    """Get all transactions for a given category, optionally filtered by year/month."""
    query = db.query(Transaction).filter(
        Transaction.Debit.isnot(None),
        Transaction.Debit > 0,
    )

    if category == "Uncategorized":
        query = query.filter(
            (Transaction.Category.is_(None)) | (Transaction.Category == "")
        )
    else:
        query = query.filter(Transaction.Category == category)

    all_txns = query.all()

    result = []
    for t in all_txns:
        dt = parse_date(t.Date)
        if not dt:
            continue
        if year is not None and dt.year != year:
            continue
        if month is not None and dt.month != month:
            continue

        result.append({
            "id": t.Id,
            "date": t.Date,
            "details": (t.Details or "")[:120],
            "debit": t.Debit or 0,
            "account": t.Account_name,
            "notes": t.Notes,
        })

    # Sort by date descending
    result.sort(key=lambda x: parse_date(x["date"]) or datetime.min, reverse=True)

    return {
        "category": category,
        "count": len(result),
        "total": round(sum(t["debit"] for t in result), 2),
        "transactions": result,
    }


@router.get("/account-analysis", summary="Account-level analysis")
async def account_analysis(
    db: Session = Depends(get_db),
) -> dict:
    """Per-account and per-type debit/credit aggregations."""
    transactions = db.query(
        Transaction.Date,
        Transaction.Debit,
        Transaction.Credit,
        Transaction.Account_name,
        Transaction.Account_type,
    ).all()

    by_account = defaultdict(lambda: {"total_debit": 0, "total_credit": 0, "count": 0})
    by_type = defaultdict(lambda: {"total_debit": 0, "total_credit": 0, "count": 0})
    monthly_accounts = defaultdict(lambda: defaultdict(lambda: {"debit": 0, "credit": 0}))

    for t in transactions:
        dt = parse_date(t.Date)
        acc = t.Account_name or "Unknown"
        acc_type = t.Account_type or "Unknown"
        debit = t.Debit or 0
        credit = t.Credit or 0

        by_account[acc]["total_debit"] += debit
        by_account[acc]["total_credit"] += credit
        by_account[acc]["count"] += 1

        by_type[acc_type]["total_debit"] += debit
        by_type[acc_type]["total_credit"] += credit
        by_type[acc_type]["count"] += 1

        if dt:
            month_key = dt.strftime("%Y-%m")
            monthly_accounts[month_key][acc]["debit"] += debit
            monthly_accounts[month_key][acc]["credit"] += credit

    account_list = sorted(
        [
            {
                "name": k,
                "total_debit": round(v["total_debit"], 2),
                "total_credit": round(v["total_credit"], 2),
                "count": v["count"],
            }
            for k, v in by_account.items()
        ],
        key=lambda x: x["total_debit"],
        reverse=True,
    )

    type_list = sorted(
        [
            {
                "type": k,
                "total_debit": round(v["total_debit"], 2),
                "total_credit": round(v["total_credit"], 2),
                "count": v["count"],
            }
            for k, v in by_type.items()
        ],
        key=lambda x: x["total_debit"],
        reverse=True,
    )

    monthly_list = sorted(
        [
            {
                "month": month,
                "accounts": [
                    {
                        "name": acc,
                        "debit": round(vals["debit"], 2),
                        "credit": round(vals["credit"], 2),
                    }
                    for acc, vals in accs.items()
                ],
            }
            for month, accs in monthly_accounts.items()
        ],
        key=lambda x: x["month"],
    )

    return {
        "by_account": account_list,
        "by_type": type_list,
        "monthly": monthly_list,
    }


@router.get("/top-transactions", summary="Top merchants and largest transactions")
async def top_transactions(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> dict:
    """Top merchants by frequency/amount, and largest individual transactions."""
    transactions = db.query(Transaction).all()

    # Group by Details text to find top merchants
    merchant_stats = defaultdict(lambda: {"count": 0, "total": 0})
    all_txns = []

    for t in transactions:
        detail = (t.Details or "Unknown").strip()
        # Take first meaningful part of the detail for grouping
        # UPI transactions often start with a pattern; simplify
        short_name = detail.split("/")[0].strip() if "/" in detail else detail[:50]
        if not short_name:
            short_name = "Unknown"

        debit = t.Debit or 0
        credit = t.Credit or 0

        if debit > 0:
            merchant_stats[short_name]["count"] += 1
            merchant_stats[short_name]["total"] += debit

        all_txns.append({
            "id": t.Id,
            "date": t.Date,
            "details": detail[:100],
            "debit": debit,
            "credit": credit,
            "account": t.Account_name,
            "category": t.Category,
        })

    top_merchants = sorted(
        [
            {"name": k, "count": v["count"], "total": round(v["total"], 2)}
            for k, v in merchant_stats.items()
            if v["count"] > 0
        ],
        key=lambda x: x["total"],
        reverse=True,
    )[:limit]

    largest_debits = sorted(
        [t for t in all_txns if t["debit"] > 0],
        key=lambda x: x["debit"],
        reverse=True,
    )[:limit]

    largest_credits = sorted(
        [t for t in all_txns if t["credit"] > 0],
        key=lambda x: x["credit"],
        reverse=True,
    )[:limit]

    # Recurring pattern detection (same merchant, 2+ occurrences)
    recurring = sorted(
        [
            {"name": k, "count": v["count"], "total": round(v["total"], 2),
             "avg": round(v["total"] / v["count"], 2)}
            for k, v in merchant_stats.items()
            if v["count"] >= 3
        ],
        key=lambda x: x["count"],
        reverse=True,
    )[:limit]

    return {
        "top_merchants": top_merchants,
        "largest_debits": largest_debits,
        "largest_credits": largest_credits,
        "recurring": recurring,
    }
