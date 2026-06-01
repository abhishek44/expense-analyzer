"""
Training script for transaction category prediction model.

Trains on L1 category names as target. Uses reviewed transactions
joined with the categories table.

Usage:
    python -m ml_model.train
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import HashingVectorizer, TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import classification_report, accuracy_score, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder

from ml_model.preprocessing import build_enhanced_text

MODEL_DIR = Path(__file__).parent
MODEL_PATH = MODEL_DIR / "category_model.joblib"
METADATA_PATH = MODEL_DIR / "model_metadata.json"
DB_PATH = Path(__file__).parent.parent / "expense_calculator.db"

MIN_SAMPLES_PER_CATEGORY = 5
MIN_TOTAL_SAMPLES = 20


def load_training_data() -> pd.DataFrame:
    """Load reviewed transactions with L1 category names."""
    import sqlite3

    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    query = """
        SELECT
            t.raw_details AS Details,
            t.notes AS Notes,
            t.debit AS Debit,
            t.credit AS Credit,
            t.account_name AS Account_name,
            t.account_type AS Account_type,
            t.flow_direction,
            t.day_of_week,
            c.name AS Category
        FROM transactions t
        JOIN categories c ON t.l1_category_id = c.id
        WHERE t.review_status != 'pending'
        AND t.l1_category_id IS NOT NULL
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare feature columns for the pipeline."""
    df = df.copy()
    df["text"] = df.apply(
        lambda r: build_enhanced_text(r["Details"], r["Notes"]), axis=1
    )
    df["amount"] = np.where(
        df["Debit"].notna(), df["Debit"], df["Credit"].fillna(0)
    )
    df["log_amount"] = np.log1p(df["amount"].abs())
    df["is_debit"] = (df["Debit"].notna()).astype(int)
    df["amount_bucket"] = pd.cut(
        df["amount"], bins=[0, 50, 200, 500, 2000, 10000, np.inf],
        labels=["tiny", "small", "medium", "large", "xlarge", "huge"]
    ).astype(str)
    df["Account_name"] = df["Account_name"].fillna("unknown")
    df["Account_type"] = df["Account_type"].fillna("unknown")
    df["flow_direction"] = df["flow_direction"].fillna("debit")
    df["day_of_week"] = df["day_of_week"].fillna(-1).astype(int).astype(str)
    return df


def build_pipeline() -> Pipeline:
    """Build the sklearn pipeline with ColumnTransformer."""
    text_transformer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        sublinear_tf=True,
        strip_accents="unicode",
        lowercase=True,
    )

    account_name_transformer = HashingVectorizer(
        n_features=32,
        ngram_range=(1, 1),
        lowercase=True,
    )

    categorical_transformer = OneHotEncoder(
        handle_unknown="ignore",
        sparse_output=True,
    )

    numeric_transformer = FunctionTransformer(func=None)

    preprocessor = ColumnTransformer(
        transformers=[
            ("text", text_transformer, "text"),
            ("acc_name", account_name_transformer, "Account_name"),
            ("cat_features", categorical_transformer, ["Account_type", "amount_bucket", "flow_direction", "day_of_week"]),
            ("numeric", numeric_transformer, ["log_amount", "is_debit"]),
        ],
        remainder="drop",
    )

    base_clf = SGDClassifier(
        loss="modified_huber",
        class_weight="balanced",
        alpha=1e-3,
        max_iter=2000,
        tol=1e-4,
        random_state=42,
    )
    classifier = CalibratedClassifierCV(base_clf, cv=2, method="sigmoid")

    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", classifier),
    ])

    return pipeline


def _determine_calibration_cv(y: pd.Series, outer_cv_splits: int = 1) -> int:
    """Determine safe cv folds for CalibratedClassifierCV."""
    min_class_count = y.value_counts().min()
    effective_min = int(min_class_count * (outer_cv_splits - 1) / outer_cv_splits) if outer_cv_splits > 1 else min_class_count
    if effective_min >= 10:
        return 5
    elif effective_min >= 6:
        return 3
    else:
        return 2


def train():
    """Main training function."""
    print("Loading training data...")
    df = load_training_data()

    if len(df) < MIN_TOTAL_SAMPLES:
        print(f"Not enough data to train. Need at least {MIN_TOTAL_SAMPLES}, found {len(df)}.")
        sys.exit(1)

    # Filter categories with too few samples
    category_counts = df["Category"].value_counts()
    valid_categories = category_counts[category_counts >= MIN_SAMPLES_PER_CATEGORY].index
    df = df[df["Category"].isin(valid_categories)]

    if len(df) < MIN_TOTAL_SAMPLES:
        print(f"After filtering rare categories, only {len(df)} samples remain.")
        sys.exit(1)

    print(f"Total samples: {len(df)} across {df['Category'].nunique()} L1 categories")
    print(f"\nCategory distribution:")
    for cat, count in category_counts.head(15).items():
        print(f"  {cat}: {count}")

    df = prepare_features(df)
    X = df[["text", "Account_name", "Account_type", "amount_bucket", "flow_direction", "day_of_week", "log_amount", "is_debit"]]
    y = df["Category"]

    # Train/Test Split (80/20)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"\nTrain/Test split: {len(X_train)} train, {len(X_test)} test")

    # Cross-validation
    n_splits = min(5, y_train.value_counts().min())
    if n_splits < 2:
        n_splits = 2
    print(f"\nOuter CV: {n_splits}-fold stratified")

    calib_cv = _determine_calibration_cv(y_train, outer_cv_splits=n_splits)
    print(f"Calibration CV folds: {calib_cv} (min class in train: {y_train.value_counts().min()})")

    pipeline = build_pipeline()
    pipeline.named_steps["classifier"].cv = calib_cv

    print(f"Running {n_splits}-fold stratified cross-validation...")
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    scores = cross_val_score(pipeline, X_train, y_train, cv=cv, scoring="accuracy")
    print(f"CV Accuracy: {scores.mean():.3f} (+/- {scores.std():.3f})")

    # Evaluate on test set
    pipeline.fit(X_train, y_train)
    y_test_pred = pipeline.predict(X_test)
    test_acc = accuracy_score(y_test, y_test_pred)
    macro_f1 = f1_score(y_test, y_test_pred, average="macro", zero_division=0)
    weighted_f1 = f1_score(y_test, y_test_pred, average="weighted", zero_division=0)

    print(f"\n{'='*60}")
    print(f"TEST SET METRICS ({len(X_test)} samples)")
    print(f"{'='*60}")
    print(f"  Accuracy:    {test_acc:.3f}")
    print(f"  Macro F1:    {macro_f1:.3f}")
    print(f"  Weighted F1: {weighted_f1:.3f}")
    print(f"{'='*60}")
    print(f"\nClassification Report:")
    print(classification_report(y_test, y_test_pred, zero_division=0))

    # Per-class recall
    report_dict = classification_report(y_test, y_test_pred, output_dict=True, zero_division=0)
    per_class = [(k, v["recall"], v["support"]) for k, v in report_dict.items()
                 if k not in ("accuracy", "macro avg", "weighted avg")]
    per_class.sort(key=lambda x: x[1])
    print("Per-class recall (worst to best):")
    for name, recall, support in per_class:
        print(f"  {name:20s}: recall={recall:.2f} (n={int(support)})")

    # Retrain on ALL data for production
    print("\nRetraining on ALL data for production...")
    final_pipeline = build_pipeline()
    final_calib_cv = _determine_calibration_cv(y)
    final_pipeline.named_steps["classifier"].cv = final_calib_cv
    final_pipeline.fit(X, y)

    train_acc = accuracy_score(y, final_pipeline.predict(X))
    print(f"Full-data Training Accuracy: {train_acc:.3f}")

    # Save
    joblib.dump(final_pipeline, MODEL_PATH)
    print(f"\nModel saved to: {MODEL_PATH}")

    metadata = {
        "trained_at": datetime.now().isoformat(),
        "num_samples": len(df),
        "num_train_samples": len(X_train),
        "num_test_samples": len(X_test),
        "num_categories": int(df["Category"].nunique()),
        "categories": sorted(y.unique().tolist()),
        "test_accuracy": float(test_acc),
        "test_macro_f1": float(macro_f1),
        "test_weighted_f1": float(weighted_f1),
        "cv_accuracy_mean": float(scores.mean()),
        "cv_accuracy_std": float(scores.std()),
        "train_accuracy": float(train_acc),
        "calibration_cv_folds": final_calib_cv,
        "model_type": "SGDClassifier (modified_huber) + CalibratedClassifierCV + TF-IDF",
        "features": ["text", "Account_name", "Account_type", "amount_bucket", "flow_direction", "day_of_week", "log_amount", "is_debit"],
        "target": "L1 category name",
        "per_class_recall": {name: round(recall, 3) for name, recall, _ in per_class},
    }
    with open(METADATA_PATH, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Metadata saved to: {METADATA_PATH}")

    return final_pipeline


if __name__ == "__main__":
    train()
