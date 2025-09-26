from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock
from django.urls import reverse
from loans.models import Customer, LoanApplication, Loan, CreditScore
from decimal import Decimal
from datetime import date

class CreateLoanUnitTest(APITestCase):

    def setUp(self):
        self.url = reverse('create-loan')
        # Create a sample customer
        self.customer = Customer.objects.create(
            first_name="Gaurang",
            last_name="Salvi",
            age=30,
            phone_number=9876543210,
            monthly_salary=50000
        )
        # Set credit score
        CreditScore.objects.create(customer=self.customer, score=80)

    def test_loan_approved_successfully(self):
        payload = {
            "customer_id": self.customer.customer_id,
            "loan_amount": 100000,
            "interest_rate": 12,
            "tenure": 12
        }

        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["loan_approved"])
        self.assertEqual(response.data["customer_id"], self.customer.customer_id)
        self.assertIsNotNone(response.data["loan_id"])
        self.assertGreater(response.data["monthly_installment"], 0)
        self.assertEqual(LoanApplication.objects.count(), 1)
        self.assertEqual(Loan.objects.count(), 1)

    def test_loan_rejected_due_to_low_credit(self):
        CreditScore.objects.filter(customer=self.customer).update(score=30)
        payload = {
            "customer_id": self.customer.customer_id,
            "loan_amount": 50000,
            "interest_rate": 10,
            "tenure": 12
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["loan_approved"])
        self.assertEqual(response.data["message"], "Credit score too low")
        self.assertEqual(Loan.objects.count(), 0)

    def test_loan_rejected_due_to_high_emi(self):
        payload = {
            "customer_id": self.customer.customer_id,
            "loan_amount": 2000000,  # very high, exceeds 50% salary EMI
            "interest_rate": 12,
            "tenure": 12
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["loan_approved"])
        self.assertEqual(response.data["message"], "EMI exceeds 50% of monthly income")

    def test_loan_rejected_due_to_exceeding_limit(self):
        self.customer.approved_limit = Decimal('100000')
        self.customer.save()
        payload = {
            "customer_id": self.customer.customer_id,
            "loan_amount": 200000,  # exceeds approved_limit
            "interest_rate": 12,
            "tenure": 12
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["loan_approved"])
        self.assertEqual(response.data["message"], "Exceeds approved credit limit")

    def test_invalid_customer_id(self):
        payload = {
            "customer_id": 999,  # non-existent
            "loan_amount": 100000,
            "interest_rate": 12,
            "tenure": 12
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)
