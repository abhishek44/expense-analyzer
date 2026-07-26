"""Integration tests for FastAPI application endpoints."""

import os
import unittest
from fastapi.testclient import TestClient

os.environ["DEBUG"] = "false"

from app.main import app


class ApiEndpointsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_check_returns_200_and_status(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("database", data)
        self.assertEqual(data["database"], "healthy")

    def test_get_transactions_returns_paginated_list(self):
        response = self.client.get("/api/transactions?skip=0&limit=10")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total", data)
        self.assertIn("data", data)
        self.assertIsInstance(data["data"], list)
        if len(data["data"]) > 1:
            dates = [t["parsed_date"] for t in data["data"] if t.get("parsed_date")]
            self.assertEqual(dates, sorted(dates, reverse=True))

    def test_get_categories_returns_list(self):
        response = self.client.get("/api/categories")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)

    def test_get_budgets_progress(self):
        response = self.client.get("/api/budgets/progress")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("progress", data)
        self.assertIn("month", data)

    def test_analytics_dashboard_with_account_name(self):
        response = self.client.get("/api/analytics/dashboard?account_name=HDFC")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("kpi", data)
        self.assertIn("monthly_trend", data)

    def test_export_transactions_includes_dates(self):
        response = self.client.get("/api/export-transactions")
        self.assertIn(response.status_code, [200, 404])
        if response.status_code == 200:
            content = response.text
            self.assertIn("statement_date", content)
            self.assertIn("mapping_date", content)

    def test_create_manual_transaction(self):
        payload = {
            "raw_date": "2026-07-25",
            "statement_date": "2026-07-24",
            "mapping_date": "2026-07-25",
            "raw_details": "Coffee Shop Test",
            "debit": 250.0,
            "account_name": "HDFC",
            "account_type": "Savings",
            "notes": "Test manual transaction",
        }
        response = self.client.post("/api/transactions", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        t = data["transaction"]
        self.assertEqual(t["raw_details"], "Coffee Shop Test")
        self.assertEqual(t["statement_date"], "2026-07-24")
        self.assertEqual(t["mapping_date"], "2026-07-25")

        # Test editing all fields of the created transaction
        txn_id = t["id"]
        update_payload = {
            "raw_details": "Coffee Shop Updated",
            "debit": 300.0,
            "account_name": "ICICI",
            "account_type": "CreditCard",
            "notes": "Updated note",
            "statement_date": "2026-07-20",
            "mapping_date": "2026-07-21",
            "review_status": "approved",
        }
        patch_res = self.client.patch(f"/api/transactions/{txn_id}", json=update_payload)
        self.assertEqual(patch_res.status_code, 200)
        updated_t = patch_res.json()["data"]
        self.assertEqual(updated_t["raw_details"], "Coffee Shop Updated")
        self.assertEqual(updated_t["debit"], 300.0)
        self.assertEqual(updated_t["amount"], -300.0)
        self.assertEqual(updated_t["account_name"], "ICICI")
        self.assertEqual(updated_t["statement_date"], "2026-07-20")
        self.assertEqual(updated_t["mapping_date"], "2026-07-21")


if __name__ == "__main__":
    unittest.main()
