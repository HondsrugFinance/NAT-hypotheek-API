"""Integration tests for monthly costs API endpoint."""

import pytest
from fastapi.testclient import TestClient


class TestCalculateEndpoint:
    """Tests for calculate monthly-costs endpoint."""

    def test_calculate_success(self, client):
        """Test successful calculation."""
        response = client.post(
            "/calculate/monthly-costs",
            json={
                "fiscal_year": 2026,
                "woz_value": 400000,
                "loan_parts": [
                    {
                        "id": "main",
                        "principal": 300000,
                        "interest_rate": 4.5,
                        "term_years": 30,
                        "loan_type": "annuity",
                        "box": 1,
                    }
                ],
                "partners": [{"id": "owner", "taxable_income": 60000, "age": 35}],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "net_monthly_cost" in data
        assert "tax_breakdown" in data
        assert "loan_parts" in data
        assert data["fiscal_year"] == 2026
        assert len(data["loan_parts"]) == 1

    def test_calculate_with_two_partners(self, client):
        """Test calculation with two partners."""
        response = client.post(
            "/calculate/monthly-costs",
            json={
                "fiscal_year": 2026,
                "woz_value": 450000,
                "loan_parts": [
                    {
                        "id": "hypotheek",
                        "principal": 350000,
                        "interest_rate": 4.2,
                        "term_years": 30,
                        "loan_type": "annuity",
                        "box": 1,
                    }
                ],
                "partners": [
                    {"id": "partner1", "taxable_income": 90000, "age": 38},
                    {"id": "partner2", "taxable_income": 45000, "age": 36},
                ],
                "partner_distribution": {"method": "optimize"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["partner_results"] is not None
        assert len(data["partner_results"]) == 2

    def test_calculate_mixed_box1_box3(self, client):
        """Test calculation with mixed box 1 and box 3 loans."""
        response = client.post(
            "/calculate/monthly-costs",
            json={
                "fiscal_year": 2026,
                "woz_value": 500000,
                "loan_parts": [
                    {
                        "id": "box1_loan",
                        "principal": 250000,
                        "interest_rate": 4.0,
                        "term_years": 30,
                        "loan_type": "annuity",
                        "box": 1,
                    },
                    {
                        "id": "box3_loan",
                        "principal": 100000,
                        "interest_rate": 4.5,
                        "term_years": 30,
                        "loan_type": "interest_only",
                        "box": 3,
                    },
                ],
                "partners": [{"id": "owner", "taxable_income": 80000, "age": 40}],
            },
        )

        assert response.status_code == 200
        data = response.json()
        # Box 3 interest should not be deductible
        assert float(data["total_interest_box3_monthly"]) > 0
        assert float(data["total_interest_box1_monthly"]) > 0

    def test_calculate_validation_error(self, client):
        """Test validation error for invalid input."""
        response = client.post(
            "/calculate/monthly-costs",
            json={
                "fiscal_year": 2026,
                "woz_value": -100,  # Invalid: negative
                "loan_parts": [],  # Invalid: empty
                "partners": [],  # Invalid: empty
            },
        )

        assert response.status_code == 422

    def test_calculate_unknown_year(self, client):
        """Test 404 for unknown fiscal year."""
        response = client.post(
            "/calculate/monthly-costs",
            json={
                "fiscal_year": 2040,  # Within valid range but no rules file
                "woz_value": 400000,
                "loan_parts": [
                    {
                        "id": "main",
                        "principal": 300000,
                        "interest_rate": 4.5,
                        "term_years": 30,
                        "loan_type": "annuity",
                        "box": 1,
                    }
                ],
                "partners": [{"id": "owner", "taxable_income": 60000, "age": 35}],
            },
        )

        assert response.status_code == 404
