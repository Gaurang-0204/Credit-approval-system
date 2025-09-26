# loans/tests/test_check_eligibility_unit.py
from unittest import TestCase
from unittest.mock import patch, MagicMock
from rest_framework.test import APIRequestFactory
from rest_framework import status

from loans.views import check_eligibility
from loans.models import Customer

class CheckEligibilityUnitTest(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.valid_payload = {
            "customer_id": 1,
            "loan_amount": 100000,
            "interest_rate": 12,
            "tenure": 12,
        }

    @patch("loans.views.evaluate_loan")
    @patch("loans.views.Customer.objects.get")
    def test_successful_eligibility(self, mock_get_customer, mock_evaluate_loan):
        # Mock customer object
        mock_customer = MagicMock()
        mock_customer.customer_id = 1
        mock_get_customer.return_value = mock_customer

        # Mock evaluate_loan output
        mock_evaluate_loan.return_value = (True, 70, 12, None, 10000)

        request = self.factory.post("/", self.valid_payload, format="json")
        response = check_eligibility(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["approval"], True)
        self.assertEqual(response.data["customer_id"], 1)
        self.assertEqual(float(response.data["monthly_installment"]), 10000)
        self.assertEqual(float(response.data["interest_rate"]), 12)

    @patch("loans.views.Customer.objects.get")
    def test_customer_not_found(self, mock_get_customer):
        # Raise the correct exception
        mock_get_customer.side_effect = Customer.DoesNotExist

        payload = self.valid_payload.copy()
        payload["customer_id"] = 999

        request = self.factory.post("/", payload, format="json")
        response = check_eligibility(request)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"], "Customer not found")

    def test_invalid_payload(self):
        # Missing required fields
        payload = {"customer_id": 1}  
        request = self.factory.post("/", payload, format="json")
        response = check_eligibility(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("loan_amount", response.data)
        self.assertIn("interest_rate", response.data)
        self.assertIn("tenure", response.data)
