"""Regression tests for the safe transaction CSV refresh script."""

import os
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DEBUG"] = "false"

from app.models import Base, Transaction
from app.scripts.update_from_csv import (
    insert_transactions,
    normalize_amount,
    repair_derived_financials,
    validate_transaction_amounts,
)
from app.services.csv_service import compute_derived_fields


class UpdateFromCsvAmountTests(unittest.TestCase):
    def test_credit_amount_is_positive_and_credit_directed(self):
        derived = compute_derived_fields("03-Mar-25", "Salary", 0.0, 1250.50)

        self.assertEqual(derived["amount"], 1250.50)
        self.assertEqual(derived["flow_direction"], "credit")

    def test_debit_amount_is_negative_and_debit_directed(self):
        derived = compute_derived_fields("03-Mar-25", "Groceries", 1250.50, 0.0)

        self.assertEqual(derived["amount"], -1250.50)
        self.assertEqual(derived["flow_direction"], "debit")

    def test_invalid_money_value_fails_instead_of_becoming_zero(self):
        with self.assertRaisesRegex(ValueError, "Credit must be a valid number"):
            normalize_amount("not-a-number", field_name="Credit", row_number=2)

    def test_non_finite_money_value_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "finite, non-negative"):
            normalize_amount("NaN", field_name="Credit", row_number=2)

    def test_debit_and_credit_cannot_both_be_positive(self):
        with self.assertRaisesRegex(ValueError, "cannot both"):
            validate_transaction_amounts(10.0, 20.0, row_number=2)

    def test_repair_corrects_an_already_corrupted_credit_row(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        self.addCleanup(engine.dispose)
        self.addCleanup(session.close)
        transaction = Transaction(
            raw_date="03-Mar-25",
            raw_details="Salary",
            debit=0.0,
            credit=1250.50,
            filename="test.csv",
            amount=0.0,
            flow_direction="debit",
        )
        session.add(transaction)
        session.commit()

        self.assertEqual(repair_derived_financials(session), 1)
        session.commit()
        session.refresh(transaction)
        self.assertEqual(transaction.amount, 1250.50)
        self.assertEqual(transaction.flow_direction, "credit")

    def test_import_derives_credit_amount_from_credit_column(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        self.addCleanup(engine.dispose)
        self.addCleanup(session.close)

        imported = insert_transactions(
            session,
            [{
                "raw_date": "03-Mar-25",
                "raw_details": "Salary",
                "Debit": "0",
                "Credit": "1250.50",
                "AccountName": "Primary",
                "AccountType": "Savings",
                "filename": "test.csv",
            }],
            {},
            {},
        )

        self.assertEqual(imported, 1)
        transaction = session.query(Transaction).one()
        self.assertEqual(transaction.amount, 1250.50)
        self.assertEqual(transaction.flow_direction, "credit")


if __name__ == "__main__":
    unittest.main()
