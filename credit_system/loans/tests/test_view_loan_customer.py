# tests.py
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from loans.models import Customer, Loan, LoanApplication
from decimal import Decimal
from datetime import date, timedelta

class ViewLoansByCustomerAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Customer
        self.customer = Customer.objects.create(
            first_name="Alice",
            last_name="Smith",
            age=30,
            phone_number=9876543210,
            monthly_salary=Decimal('50000'),
            approved_limit=Decimal('1000000')
        )

        # Loan 1 (approved)
        self.loan1 = Loan.objects.create(
            customer=self.customer,
            loan_amount=Decimal('500000'),
            tenure=12,
            interest_rate=Decimal('12.0'),
            monthly_repayment=Decimal('44444.44'),
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=335)
        )
        self.application1 = LoanApplication.objects.create(
            customer=self.customer,
            loan=self.loan1,
            requested_amount=self.loan1.loan_amount,
            requested_interest_rate=self.loan1.interest_rate,
            requested_tenure=self.loan1.tenure,
            status='APPROVED',
            approved_amount=self.loan1.loan_amount,
            approved_interest_rate=self.loan1.interest_rate,
            monthly_installment=self.loan1.monthly_repayment
        )

        # Loan 2 (not approved)
        self.loan2 = Loan.objects.create(
            customer=self.customer,
            loan_amount=Decimal('200000'),
            tenure=6,
            interest_rate=Decimal('10.0'),
            monthly_repayment=Decimal('35000'),
            start_date=date.today() - timedelta(days=15),
            end_date=date.today() + timedelta(days=165)
        )
        # No application → not approved

    def test_view_loans_success(self):
        url = f'/api/view-loans/{self.customer.customer_id}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 2)

        # Check first loan (approved)
        loan1_data = next(l for l in data if l['loan_id'] == self.loan1.loan_id)
        self.assertTrue(loan1_data['loan_approved'])
        self.assertEqual(loan1_data['loan_amount'], float(self.loan1.loan_amount))

        # Check second loan (not approved)
        loan2_data = next(l for l in data if l['loan_id'] == self.loan2.loan_id)
        self.assertFalse(loan2_data['loan_approved'])
        self.assertEqual(loan2_data['loan_amount'], float(self.loan2.loan_amount))

    def test_customer_not_found(self):
        url = f'/api/view-loans/9999/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json()['error'], 'Customer not found')
