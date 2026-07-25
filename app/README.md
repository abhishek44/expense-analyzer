# Expense Tracker — Web App

> The web-facing frontend and API layer of the Expense Analyzer platform.  
> Built with **FastAPI** (backend) and **vanilla HTML/CSS/JS** (frontend), served as a single deployable unit.

---

## Quick Start

```bash
# From the project root, with the virtual environment activated:
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

| URL                              | Purpose                         |
| -------------------------------- | ------------------------------- |
| http://localhost:8001             | Transaction Manager (main UI)   |
| http://localhost:8001/analytics   | Analytics Dashboard             |
| http://localhost:8001/docs        | Swagger UI (interactive API)    |
| http://localhost:8001/redoc       | ReDoc (API reference)           |
| http://localhost:8001/health      | Health check endpoint           |

---

## App Structure

```
app/
├── main.py                # FastAPI app, lifespan init, CORS, route mounting
├── config.py              # pydantic-settings based config (env / .env file)
├── database.py            # SQLAlchemy engine + session (SQLite, StaticPool)
├── models.py              # ORM: Transaction, Category, MerchantMapping, Account
├── schemas.py             # Shared Pydantic response models
├── routers/
│   ├── csv_upload.py      # Transactions: CRUD, upload, review, export, import
│   ├── categories.py      # 2-level category hierarchy CRUD
│   ├── accounts.py        # Account management with balance computation
│   ├── analytics.py       # Spending analytics + breakdowns
│   └── ml_predict.py      # ML model training, prediction, evaluation
├── services/
│   └── csv_service.py     # CSV parsing, field derivation, merchant extraction
└── static/
    ├── index.html         # Transaction Manager SPA (~760 lines)
    └── analytics.html     # Analytics Dashboard SPA (~1368 lines)
```

---

## Frontend Pages

Both pages are single-file SPAs using **TailwindCSS CDN**, **Manrope** font, **Material Symbols** icons, and a dark theme with a custom color palette.

### Transaction Manager (`index.html` — served at `/`)

A mobile-first SPA with bottom navigation and client-side routing. All state is managed in a single `appState` object and all API calls go through a central `api` helper.

#### Screens / Routes

| Route        | Nav Tab     | Purpose                                             |
| ------------ | ----------- | --------------------------------------------------- |
| `home`       | Home        | Dashboard with pending/reviewed counts + CSV export  |
| `upload`     | (Settings)  | CSV file upload with drag-and-drop                   |
| `files`      | Files       | List uploaded files with stats, delete file batches   |
| `list`       | (from files)| Transaction list with status filter chips (All/Pending/Reviewed), infinite scroll |
| `details`    | (from list) | Transaction detail + review form with L1/L2 category dropdowns, merchant suggestions, delete |
| `addExpense` | FAB (+)     | Manual transaction entry form                        |
| `accounts`   | Accounts    | Account list with balances, add/delete accounts      |
| `categories` | Categories  | Full L1/L2 hierarchy view, add/edit/delete categories with color picker |
| `settings`   | Settings    | Upload CSV link + danger zone (clear all data)       |

#### Key UI Features

- **Bottom navigation bar** — 6 tabs: Home, Files, Accounts, Categories, Analytics (links to `/analytics`), Settings
- **Filter chips** — Toggle between All / Pending / Reviewed transactions
- **Merchant suggestions** — When reviewing a transaction, a green/yellow banner shows the merchant's historical category if available
- **Cascading category selects** — L1 dropdown populates L2 children dynamically
- **Inline category management** — Add L2 sub-categories directly under each L1 on the categories screen
- **FAB (Floating Action Button)** — Quick-add manual expense from file list or transaction list views
- **Transaction cards** — Show merchant name (or cleaned details), amount with debit/credit coloring, review status badge, and date

#### Client-Side Router

```js
// Simple hash-less router — screens render to #app div
router.navigate('details', { id: 123 });
// Renders screens.details(123) → screens.initDetails(123)
```

Each screen has two parts:
1. **`screens.<name>()`** — Returns the HTML template string
2. **`screens.init<Name>()`** — Binds event handlers, fetches data, populates dynamic elements

---

### Analytics Dashboard (`analytics.html` — served at `/analytics`)

A data-rich dashboard with **Chart.js** visualizations. Uses a tabbed layout with 4 sections.

#### Tab 1: Overview

- **Summary cards** — Total Spent, Total Income, Net Flow (color-coded positive/negative)
- **Monthly trend chart** — Grouped bar chart (debit + credit) with a net flow line overlay
- **Spending heatmap** — GitHub-style contribution heatmap showing daily spending intensity
- **Monthly breakdown table** — Tabular view with debit, credit, and net per month

#### Tab 2: Categories

- **Period filter** — Year buttons + month pills for drilling down to specific periods
- **Category donut chart** — Proportional spending by L1 category with a color-coded legend
- **Category trends chart** — Stacked bar chart showing category composition over months
- **Category ranking list** — Clickable list ranked by total spend; tapping opens a bottom-sheet modal
- **Transaction drill-down modal** — Slide-up panel showing individual transactions for a category, with a scrollable table

#### Tab 3: Accounts

- **Account summary cards** — Total debit, total credit, and transaction count per account
- **Account type breakdown** — Grouped by type (Savings, Credit Card, etc.)
- **Monthly account chart** — Stacked bar showing per-account spending by month

#### Tab 4: Top

- **Top merchants table** — Highest total spend merchants with transaction counts
- **Largest transactions** — Biggest single debits and credits
- **Recurring patterns** — Merchants with 3+ transactions showing frequency and average amount

#### Chart.js Configuration

All charts use a consistent dark theme:
- Custom tooltip styling matching the dark surface colors
- INR currency formatting (`₹`) in tooltips and axis labels
- A 20-color palette for category differentiation
- Responsive sizing with `maintainAspectRatio: false`

---

## API Reference

All API endpoints are prefixed with `/api`. Full interactive documentation is at `/docs`.

### Transactions (`/api`)

| Method   | Endpoint                           | Description                                      |
| -------- | ---------------------------------- | ------------------------------------------------ |
| `POST`   | `/upload-csv`                      | Upload bank statement CSV (multipart form)        |
| `GET`    | `/transactions`                    | Paginated list with filters (status, account, date, category) |
| `GET`    | `/transactions/{id}`               | Single transaction with category relationship names |
| `POST`   | `/transactions`                    | Create manual transaction                         |
| `PATCH`  | `/transactions/{id}`               | Update notes, account fields                      |
| `DELETE` | `/transactions/{id}`               | Delete single transaction                         |
| `POST`   | `/transactions/{id}/review`        | Assign categories + approve/reject                |
| `GET`    | `/merchant-suggestion/{id}`        | Merchant-based category suggestion                |
| `GET`    | `/tables`                          | Stats: total, pending, reviewed counts            |
| `GET`    | `/filter-options`                  | Distinct account names and types for dropdowns    |
| `GET`    | `/uploaded-files`                  | List files with per-file pending/reviewed counts  |
| `DELETE` | `/uploaded-files/{filename}`       | Delete all transactions from a file               |
| `DELETE` | `/tables/{table_name}/clear`       | Clear entire transactions table                   |
| `GET`    | `/export-transactions`             | Download all transactions as CSV                  |
| `POST`   | `/import-transactions`             | Re-import edited CSV (upsert by ID)               |

#### Transaction Filters (`GET /transactions`)

| Param           | Type   | Description                              |
| --------------- | ------ | ---------------------------------------- |
| `skip`          | int    | Pagination offset (default: 0)           |
| `limit`         | int    | Page size (default: 100)                 |
| `status_filter`  | string | `pending` / `approved` / `rejected`     |
| `filename_filter`| string | Exact match on source filename           |
| `account_name`  | string | Partial match (ILIKE)                    |
| `account_type`  | string | Partial match (ILIKE)                    |
| `l1_category_id`| string | Exact category UUID                      |
| `date_from`     | string | `YYYY-MM-DD` inclusive start             |
| `date_to`       | string | `YYYY-MM-DD` inclusive end               |

#### Review Flow

When reviewing a transaction (`POST /transactions/{id}/review`):

```json
{
  "l1_category_id": "uuid-here",
  "l2_category_id": "uuid-or-null",
  "notes": "optional note",
  "review_status": "approved"
}
```

Side effects:
1. Sets `categorised_by = "user"`, `l2_confidence = 1.0`, `reviewed_at = now()`
2. Creates or updates `merchant_mappings` for the transaction's merchant
3. If the merchant was previously categorised differently, marks it as `is_ambiguous = 1`

#### CSV Upload Format

Required columns: `Date`, `Details`, `Debit`, `Credit`, `AccountName`, `AccountType`

On upload, the server automatically computes:
- `amount` (signed), `flow_direction`, `parsed_date` (normalised to `YYYY-MM-DD`)
- `day_of_week`, `month`, `is_weekend`
- `merchant_name` (extracted + normalised), `is_platform_merchant`
- `cleaned_details` (for ML features)

#### Export/Import Round-Trip

1. **Export** (`GET /export-transactions`) — Downloads CSV with all fields including category names
2. **Edit** — Modify categories, notes, etc. in a spreadsheet
3. **Import** (`POST /import-transactions`) — Re-uploads the CSV:
   - Rows with matching `id` → **updated** in-place
   - Rows without `id` → **inserted** as new
   - Category names resolved to IDs via case-insensitive lookup

---

### Categories (`/api/categories`)

| Method   | Endpoint      | Description                                        |
| -------- | ------------- | -------------------------------------------------- |
| `GET`    | (root)        | All categories, optionally nested (L2 under L1)    |
| `GET`    | `/{id}`       | Single category with children                      |
| `POST`   | (root)        | Create (L2 requires `parent_id`)                   |
| `POST`   | `/batch`      | Batch create, skipping duplicates                  |
| `PATCH`  | `/{id}`       | Update name, color, archive status                 |
| `DELETE` | `/{id}`       | Delete (L1 cascades to children)                   |

**Unique constraint:** `(name, parent_id)` — no duplicate names under the same parent.

**Query params for GET:**
- `level` (int) — Filter by 1 or 2
- `domain` (string) — Filter by `NECESSITIES`, `LIFESTYLE`, `FINANCIAL`, `INCOME`
- `include_children` (bool, default `true`) — Nest L2 under L1 in response

---

### Accounts (`/api`)

| Method   | Endpoint              | Description                            |
| -------- | --------------------- | -------------------------------------- |
| `GET`    | `/accounts`           | All accounts with computed balances     |
| `GET`    | `/accounts/{id}`      | Single account with balance             |
| `POST`   | `/accounts`           | Create account                          |
| `POST`   | `/accounts/batch`     | Batch upsert (mobile sync)              |
| `PATCH`  | `/accounts/{id}`      | Update fields                           |
| `DELETE` | `/accounts/{id}`      | Delete account                          |
| `GET`    | `/account-types`      | List valid account types                |

**Balance computation:** `opening_balance + SUM(credits) - SUM(debits)` — computed on the fly by joining with transactions on `account_name`.

**Account types:** `SAVINGS`, `CURRENT`, `CREDIT_CARD`, `CASH`, `WALLET`, `INVESTMENT`

**Sync support:** `GET /accounts?since=2025-01-01T00:00:00` for incremental sync. `POST /accounts/batch` for mobile app upsert with timestamp-based conflict resolution.

---

### Analytics (`/api/analytics`)

| Method | Endpoint                  | Description                                        |
| ------ | ------------------------- | -------------------------------------------------- |
| `GET`  | `/spending-overview`      | Monthly totals, daily amounts, net flow             |
| `GET`  | `/category-breakdown`     | L1 spending totals, percentages, monthly trends     |
| `GET`  | `/category-transactions`  | Individual transactions for a category              |
| `GET`  | `/account-analysis`       | Per-account and per-type debit/credit totals        |
| `GET`  | `/top-transactions`       | Top merchants, largest transactions, recurring      |

**`/category-breakdown` params:**
- `months` (int, 1-24, default 6) — Lookback window
- `year` (int) — Filter to year
- `month` (int, 1-12) — Filter to month (requires `year`)

**`/category-transactions` params:**
- `category` (string, required) — L1 category name (or `"Uncategorized"`)
- `year`, `month` — Optional date filters

---

### ML Predictions (`/api/ml`)

| Method | Endpoint           | Description                                    |
| ------ | ------------------ | ---------------------------------------------- |
| `POST` | `/predict`         | Predict L1 category for single transaction     |
| `POST` | `/predict-pending` | Batch predict for all (or specific) pending    |
| `POST` | `/train`           | Train model from reviewed data (min 20)        |
| `GET`  | `/status`          | Model availability, metadata, counts           |
| `POST` | `/evaluate`        | Accuracy + sample mismatches vs reviewed data  |

**Training pipeline:** `reviewed transactions → TF-IDF features → classifier → saved model`

---

## Data Model

### Transaction

| Field Group         | Key Columns                                                        |
| ------------------- | ------------------------------------------------------------------ |
| **Raw (immutable)** | `raw_date`, `raw_details`, `debit`, `credit`, `account_name`, `account_type`, `filename` |
| **Derived**         | `amount`, `flow_direction`, `parsed_date`, `day_of_week`, `month`, `is_weekend` |
| **Merchant**        | `merchant_name`, `is_platform_merchant`, `cleaned_details`         |
| **Categories**      | `l1_category_id` (FK), `l2_category_id` (FK), `l2_confidence`, `categorised_by` |
| **Review**          | `review_status` (`pending`/`approved`/`rejected`), `reviewed_at`   |

### Category (2-level hierarchy)

```
L1: Food & Dining  (domain=NECESSITIES, color=#FF6B35)
  L2: Restaurants
  L2: Delivery
  L2: Snacks
```

- `id` (UUID), `name`, `level` (1 or 2), `parent_id` (FK → self), `domain`, `color_hex`
- Unique constraint: `(name, parent_id)`

### MerchantMapping

Auto-populated when transactions are reviewed. Tracks `merchant_name → default category`, `occurrence_count`, and `is_ambiguous` flag.

### Account

`id`, `name`, `account_type`, `currency`, `opening_balance`, `is_archived`. Balance computed dynamically from transactions.

---

## Design System

| Token               | Value            | Usage                           |
| -------------------- | ---------------- | ------------------------------- |
| `primary`            | `#137fec`        | Buttons, active states, links   |
| `background-dark`    | `#101922`        | Page background                 |
| `surface-dark`       | `#1c232d`        | Cards, modals, inputs           |
| `border-dark`        | `#2a3441`        | Borders, dividers               |
| `text-secondary`     | `#9dabb9`        | Labels, secondary text          |
| Font                 | Manrope          | All text                        |
| Icons                | Material Symbols  | Outlined, weight 400            |

---

## Configuration

Via environment variables or `.env` file (loaded by pydantic-settings):

| Variable               | Default                            | Description                  |
| ---------------------- | ---------------------------------- | ---------------------------- |
| `DATABASE_URL`         | `sqlite:///./expense_calculator.db`| SQLite path                  |
| `DEBUG`                | `True`                             | SQLAlchemy echo              |
| `MAX_FILE_SIZE_MB`     | `10`                               | Upload size limit            |
| `ALLOWED_EXTENSIONS`   | `{".csv"}`                         | Accepted file types          |

---

## Key Implementation Notes

1. **StaticPool** — The SQLite engine uses `StaticPool` with `check_same_thread=False`, meaning a single connection is shared. This is fine for single-user local use but not suitable for production multi-user deployment.

2. **Derived fields** — All derived fields (`amount`, `parsed_date`, `merchant_name`, etc.) are computed at ingestion time in `csv_service.compute_derived_fields()`. They are stored denormalized for query performance.

3. **Category resolution** — The export CSV stores category *names*; on re-import, names are resolved to IDs via case-insensitive lookup. This allows external editing without needing to know UUIDs.

4. **Merchant suggestion flow** — On the detail screen, the frontend calls `GET /merchant-suggestion/{id}`. If the merchant has been seen before with a consistent category, a green "Apply" banner appears. If ambiguous (multiple categories), a yellow warning prompts for notes.

5. **Platform merchants** — A hardcoded set (Amazon, Flipkart, Swiggy, Zepto, etc.) is flagged via `is_platform_merchant`. This is used by the ML model as a feature.
