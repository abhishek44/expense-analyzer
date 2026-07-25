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


if __name__ == "__main__":
    unittest.main()
