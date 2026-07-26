"""Analytics API router — unified dashboard endpoint."""

from datetime import datetime
from typing import Optional
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Transaction, Category, ReviewStatus

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

# L2 category name used for CC bill reconciliation tracking
CC_BILL_L2_NAME = "Credit Card Bill"


@router.get("/dashboard", summary="Unified analytics dashboard data")
async def dashboard(
    date_from: Optional[str] = Query(None, description="Start month YYYY-MM"),
    date_to: Optional[str] = Query(None, description="End month YYYY-MM"),
    account_type: Optional[str] = Query(None, description="Savings or CreditCard"),
    account_name: Optional[str] = Query(None, description="Specific account name"),
    categories: Optional[str] = Query(None, description="Comma-separated L1 category names"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Single endpoint powering the entire analytics dashboard.

    Rules:
    - True Income: SUM(all credits) — no exclusions
    - True Expenses: SUM(all debits) — no exclusions
    - CC Bill Reconciliation: debits vs credits for 'Credit Card Bill' L2
    - Pivot table: L1 → L2 hierarchy with credit, debit, difference columns
    """

    # ── Build lookups ──────────────────────────────────────────────────────
    all_l1_cats = db.query(Category).filter(
        Category.level == 1, Category.is_archived == 0
    ).order_by(Category.name).all()

    all_l2_cats = db.query(Category).filter(
        Category.level == 2, Category.is_archived == 0
    ).all()

    from sqlalchemy import func
    eff_date_expr = func.coalesce(func.strftime("%Y-%m-%d", Transaction.mapping_date), Transaction.parsed_date)

    all_dates = db.query(eff_date_expr.label("eff_date")).filter(
        eff_date_expr.isnot(None)
    ).distinct().all()
    all_years = sorted(set(d[0][:4] for d in all_dates if d[0]), reverse=True)
    all_account_types = [
        r[0] for r in db.query(Transaction.account_type).distinct().filter(
            Transaction.account_type.isnot(None)
        ).all()
    ]

    # Lookup maps
    l1_id_to_name = {c.id: c.name for c in all_l1_cats}
    l1_id_to_color = {c.id: c.color_hex for c in all_l1_cats}
    l1_name_to_id = {c.name: c.id for c in all_l1_cats}
    l2_id_to_name = {c.id: c.name for c in all_l2_cats}
    l2_id_to_parent = {c.id: c.parent_id for c in all_l2_cats}

    # CC Bill L2 ID for reconciliation
    cc_bill_l2_ids = set(c.id for c in all_l2_cats if c.name == CC_BILL_L2_NAME)

    # Parse category filter
    selected_categories = [c.strip() for c in categories.split(",") if c.strip()] if categories else []
    selected_cat_ids = set()
    if selected_categories:
        for cat in all_l1_cats:
            if cat.name in selected_categories:
                selected_cat_ids.add(cat.id)

    # ── Build FY options ──────────────────────────────────────────────────
    fy_options = []
    if all_years:
        min_year = min(int(y) for y in all_years)
        max_year = max(int(y) for y in all_years)
        for start_year in range(max_year, min_year - 2, -1):
            fy_label = f"FY {str(start_year)[-2:]}-{str(start_year + 1)[-2:]}"
            fy_from = f"{start_year}-04"
            fy_to = f"{start_year + 1}-03"
            fy_options.append({"label": fy_label, "date_from": fy_from, "date_to": fy_to})

    # ── Fetch transactions ────────────────────────────────────────────────
    base_query = db.query(Transaction).filter(
        eff_date_expr.isnot(None),
        Transaction.review_status == ReviewStatus.APPROVED.value
    )

    if date_from:
        base_query = base_query.filter(eff_date_expr >= date_from + "-01")
    if date_to:
        base_query = base_query.filter(eff_date_expr <= date_to + "-31")
    if account_type:
        # Normalize incoming request value to check match
        norm_type = account_type.lower().replace(" ", "").replace("_", "")
        # Normalize DB values for matching
        base_query = base_query.filter(
            func.lower(func.replace(func.replace(Transaction.account_type, " ", ""), "_", "")) == norm_type
        )
    if account_name:
        base_query = base_query.filter(Transaction.account_name.ilike(f"%{account_name}%"))
    if selected_cat_ids:
        base_query = base_query.filter(Transaction.l1_category_id.in_(selected_cat_ids))

    all_txns = base_query.with_entities(
        eff_date_expr.label("eff_date"),
        Transaction.debit,
        Transaction.credit,
        Transaction.account_type,
        Transaction.l1_category_id,
        Transaction.l2_category_id,
    ).order_by(eff_date_expr.asc()).all()

    # ── Compute everything in a single pass ───────────────────────────────
    # Primary account types to show in pivot table columns
    primary_account_types = ["Savings", "CreditCard"]
    extra_account_types = [a for a in sorted(all_account_types) if a not in primary_account_types and a.lower() not in ["savings", "creditcard"]]
    pivot_account_types = primary_account_types + extra_account_types

    total_income = 0.0
    total_expense = 0.0
    monthly_income = defaultdict(float)
    monthly_expenses = defaultdict(float)
    category_totals = defaultdict(float)        # L1 debit totals for donut
    l2_totals = defaultdict(float)              # L2 debit totals for bar chart

    # CC Bill reconciliation
    cc_bill_debits = 0.0
    cc_bill_credits = 0.0

    # Pivot table structure:
    # L1 -> { "label": name, "by_account": { acc: { "debit": 0, "credit": 0 } }, "total_debit": 0, "total_credit": 0, "difference": 0 }
    def make_bucket(label):
        return {
            "name": label,
            "by_account": {acc: {"debit": 0.0, "credit": 0.0} for acc in pivot_account_types},
            "total_debit": 0.0,
            "total_credit": 0.0,
            "difference": 0.0,
        }

    pivot_l1 = {}
    pivot_l2 = defaultdict(dict)

    # L1 categories excluded from expense distribution charts (not from KPIs)
    non_expense_l1_names = {"Financial", "Income"}

    for t in all_txns:
        month_key = t.eff_date[:7]
        debit = t.debit or 0.0
        credit = t.credit or 0.0
        l1_name = l1_id_to_name.get(t.l1_category_id, "Uncategorized")
        l2_name = l2_id_to_name.get(t.l2_category_id, "(blank)")
        acc_type = t.account_type or "Unknown"

        # Match account type to pivot columns
        matched_acc = next((a for a in pivot_account_types if a.lower() == acc_type.lower()), acc_type)
        if matched_acc not in pivot_account_types:
            pivot_account_types.append(matched_acc)
            # update existing buckets
            for bucket in pivot_l1.values():
                bucket["by_account"][matched_acc] = {"debit": 0.0, "credit": 0.0}
            for l1_k in pivot_l2:
                for bucket in pivot_l2[l1_k].values():
                    bucket["by_account"][matched_acc] = {"debit": 0.0, "credit": 0.0}

        # ── KPI Calculations matching pivot_table_viewer.html ─────────────────
        if l1_name.lower() == "income":
            # Income category is treated as inflow: Credit - Debit
            inflow = credit - debit
            total_income += inflow
            if credit > 0:
                monthly_income[month_key] += credit
        else:
            # Every non-income category is treated as expense: Debit - Credit (credits/refunds reduce expense)
            outflow = debit - credit
            total_expense += outflow
            if debit > 0:
                monthly_expenses[month_key] += debit

        # ── Category distribution (charts only — excludes Financial/Income)
        if debit > 0 and l1_name and l1_name not in non_expense_l1_names:
            category_totals[l1_name] += debit
        if debit > 0 and l2_name and l2_name != "(blank)" and l1_name and l1_name not in non_expense_l1_names:
            l2_totals[l2_name] += debit

        # ── CC Bill reconciliation ────────────────────────────────────
        if t.l2_category_id in cc_bill_l2_ids:
            cc_bill_debits += debit
            cc_bill_credits += credit

        # ── Pivot table ───────────────────────────────────────────────
        if l1_name not in pivot_l1:
            pivot_l1[l1_name] = make_bucket(l1_name)

        l1_b = pivot_l1[l1_name]
        l1_b["by_account"][matched_acc]["debit"] += debit
        l1_b["by_account"][matched_acc]["credit"] += credit
        l1_b["total_debit"] += debit
        l1_b["total_credit"] += credit

        if l2_name and l2_name != "(blank)":
            if l2_name not in pivot_l2[l1_name]:
                pivot_l2[l1_name][l2_name] = make_bucket(l2_name)
            l2_b = pivot_l2[l1_name][l2_name]
            l2_b["by_account"][matched_acc]["debit"] += debit
            l2_b["by_account"][matched_acc]["credit"] += credit
            l2_b["total_debit"] += debit
            l2_b["total_credit"] += credit

    # Round bucket values and compute differences
    for l1_b in pivot_l1.values():
        l1_b["total_debit"] = round(l1_b["total_debit"], 2)
        l1_b["total_credit"] = round(l1_b["total_credit"], 2)
        l1_b["difference"] = round(l1_b["total_credit"] - l1_b["total_debit"], 2)
        for acc in l1_b["by_account"]:
            l1_b["by_account"][acc]["debit"] = round(l1_b["by_account"][acc]["debit"], 2)
            l1_b["by_account"][acc]["credit"] = round(l1_b["by_account"][acc]["credit"], 2)

    for l1_k in pivot_l2:
        for l2_b in pivot_l2[l1_k].values():
            l2_b["total_debit"] = round(l2_b["total_debit"], 2)
            l2_b["total_credit"] = round(l2_b["total_credit"], 2)
            l2_b["difference"] = round(l2_b["total_credit"] - l2_b["total_debit"], 2)
            for acc in l2_b["by_account"]:
                l2_b["by_account"][acc]["debit"] = round(l2_b["by_account"][acc]["debit"], 2)
                l2_b["by_account"][acc]["credit"] = round(l2_b["by_account"][acc]["credit"], 2)

    total_income = round(total_income, 2)
    total_expense = round(total_expense, 2)
    net_savings = round(total_income - total_expense, 2)
    savings_rate = round((net_savings / total_income * 100), 2) if total_income != 0 else 0.0

    # ── Monthly trend with cumulative ─────────────────────────────────────
    all_months = sorted(set(list(monthly_income.keys()) + list(monthly_expenses.keys())))
    cumulative = 0.0
    monthly_trend = []
    for m in all_months:
        inc = monthly_income[m]
        exp = monthly_expenses[m]
        cumulative += inc - exp
        monthly_trend.append({
            "month": m,
            "income": round(inc, 2),
            "expenses": round(exp, 2),
            "cumulative": round(cumulative, 2),
        })

    # ── L1 Category distribution (charts) ─────────────────────────────────
    grand_expense_total = sum(category_totals.values())
    category_distribution = sorted(
        [
            {
                "name": name,
                "total": round(total, 2),
                "percentage": round((total / grand_expense_total * 100) if grand_expense_total > 0 else 0, 1),
                "color": l1_id_to_color.get(
                    next((c.id for c in all_l1_cats if c.name == name), None), "#666666"
                ),
            }
            for name, total in category_totals.items()
        ],
        key=lambda x: x["total"],
        reverse=True,
    )

    # ── L2 Sub-category distribution (charts) ─────────────────────────────
    grand_l2_total = sum(l2_totals.values())
    l2_distribution = sorted(
        [
            {
                "name": name,
                "total": round(total, 2),
                "percentage": round((total / grand_l2_total * 100) if grand_l2_total > 0 else 0, 1),
            }
            for name, total in l2_totals.items()
        ],
        key=lambda x: x["total"],
        reverse=True,
    )

    # ── CC Bill Reconciliation ────────────────────────────────────────────
    cc_bill_difference = round(cc_bill_debits - cc_bill_credits, 2)
    cc_reconciliation = {
        "total_debits": round(cc_bill_debits, 2),
        "total_credits": round(cc_bill_credits, 2),
        "difference": cc_bill_difference,
        "status": "balanced" if abs(cc_bill_difference) < 1 else "unbalanced",
    }

    # ── Pivot table array ──────────────────────────────────────────────────
    pivot_table = []
    for l1_name in sorted(pivot_l1.keys()):
        l1_b = pivot_l1[l1_name]
        children = []
        if l1_name in pivot_l2:
            for l2_name in sorted(pivot_l2[l1_name].keys()):
                children.append(pivot_l2[l1_name][l2_name])

        l1_b["children"] = sorted(children, key=lambda x: x["total_debit"], reverse=True)
        pivot_table.append(l1_b)

    # Grand total row calculation
    grand_by_account = {acc: {"debit": 0.0, "credit": 0.0} for acc in pivot_account_types}
    grand_total_debit = 0.0
    grand_total_credit = 0.0

    for r in pivot_table:
        grand_total_debit += r["total_debit"]
        grand_total_credit += r["total_credit"]
        for acc in pivot_account_types:
            grand_by_account[acc]["debit"] += r["by_account"][acc]["debit"]
            grand_by_account[acc]["credit"] += r["by_account"][acc]["credit"]

    grand_total_debit = round(grand_total_debit, 2)
    grand_total_credit = round(grand_total_credit, 2)
    grand_diff = round(grand_total_credit - grand_total_debit, 2)
    for acc in pivot_account_types:
        grand_by_account[acc]["debit"] = round(grand_by_account[acc]["debit"], 2)
        grand_by_account[acc]["credit"] = round(grand_by_account[acc]["credit"], 2)

    # ── Response ──────────────────────────────────────────────────────────
    return {
        "filters": {
            "available_years": [int(y) for y in all_years],
            "available_account_types": sorted(all_account_types),
            "available_categories": [{"id": c.id, "name": c.name} for c in all_l1_cats],
            "fy_options": fy_options,
            "applied": {
                "date_from": date_from,
                "date_to": date_to,
                "account_type": account_type,
                "categories": selected_categories,
            },
        },
        "kpi": {
            "true_income": total_income,
            "true_expenses": total_expense,
            "net_savings": net_savings,
            "savings_rate": savings_rate,
        },
        "monthly_trend": monthly_trend,
        "category_distribution": category_distribution,
        "l2_distribution": l2_distribution,
        "cc_reconciliation": cc_reconciliation,
        "account_types": pivot_account_types,
        "pivot_table": pivot_table,
        "pivot_grand_total": {
            "by_account": grand_by_account,
            "total_debit": grand_total_debit,
            "total_credit": grand_total_credit,
            "difference": grand_diff,
        },
    }
