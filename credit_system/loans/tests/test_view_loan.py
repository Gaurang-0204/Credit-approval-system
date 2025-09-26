from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from loans.models import Customer, Loan, LoanApplication
from decimal import Decimal
from datetime import date, timedelta
from django.urls import reverse


class ViewLoanAPITest(TestCase):
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

        # Loan
        self.loan = Loan.objects.create(
            customer=self.customer,
            loan_amount=Decimal('500000'),
            tenure=12,
            interest_rate=Decimal('12.0'),
            monthly_repayment=Decimal('44444.44'),
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=335)
        )

        # LoanApplication approved
        LoanApplication.objects.create(
            customer=self.customer,
            loan=self.loan,
            requested_amount=self.loan.loan_amount,
            requested_interest_rate=self.loan.interest_rate,
            requested_tenure=self.loan.tenure,
            status='APPROVED',
            approved_amount=self.loan.loan_amount,
            approved_interest_rate=self.loan.interest_rate,
            monthly_installment=self.loan.monthly_repayment
        )

    def test_view_loan_success(self):
        response = self.client.get(f'/api/view-loan/{self.loan.loan_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(data['loan_id'], self.loan.loan_id)
        self.assertEqual(data['customer']['customer_id'], self.customer.customer_id)
        self.assertEqual(data['loan_amount'], float(self.loan.loan_amount))
        self.assertEqual(data['interest_rate'], float(self.loan.interest_rate))
        self.assertEqual(data['tenure'], self.loan.tenure)
        self.assertEqual(data['monthly_installment'], float(self.loan.monthly_repayment))
        self.assertTrue(data['loan_approved'])

    def test_view_loan_not_found(self):
        url = reverse('view-loan', kwargs={'loan_id': 9999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json()['error'], 'Loan not found')
