from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from loans.models import Customer

class CustomerRegisterUnitTest(APITestCase):

    def setUp(self):
        self.url = reverse('customer-register')

    def test_register_customer_success(self):
        """
        ✅ Test successful registration
        """
        data = {
            "first_name": "Gaurang",
            "last_name": "Salvi",
            "age": 30,
            "monthly_income": 50000,
            "phone_number": 9876543210
        }

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("customer_id", response.data)
        self.assertEqual(response.data["name"], "Gaurang Salvi")
        self.assertEqual(response.data["approved_limit"], 1800000)
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(Customer.objects.first().phone_number, 9876543210)

    def test_register_customer_invalid_income(self):
        """
        ❌ Registration fails if monthly_income is zero or negative
        """
        data = {
            "first_name": "Jane",
            "last_name": "Doe",
            "age": 28,
            "monthly_income": 0,
            "phone_number": 1234567899
        }

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("monthly_income", response.data)
        self.assertEqual(Customer.objects.count(), 0)

    def test_register_customer_invalid_phone(self):
        """
        ❌ Registration fails if phone number is invalid
        """
        data = {
            "first_name": "Sam",
            "last_name": "Smith",
            "age": 40,
            "monthly_income": 60000,
            "phone_number": 12345  # invalid
        }

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone_number", response.data)
        self.assertEqual(Customer.objects.count(), 0)
