from rest_framework import serializers
from .models import Customer,Loan
import math

from rest_framework import serializers
from .models import Customer

class CustomerRegisterSerializer(serializers.ModelSerializer):
    monthly_income = serializers.IntegerField(write_only=True)

    class Meta:
        model = Customer
        fields = ['first_name', 'last_name', 'age', 'monthly_income', 'phone_number']

    # ---------------------------
    # VALIDATIONS
    # ---------------------------
    def validate_age(self, value):
        if value <= 0:
            raise serializers.ValidationError("Age must be greater than 0.")
        return value

    def validate_monthly_income(self, value):
        if value <= 0:
            raise serializers.ValidationError("Monthly income must be greater than 0.")
        return value

    def validate_phone_number(self, value):
        if not str(value).isdigit() or len(str(value)) != 10:
            raise serializers.ValidationError("Phone number must be a valid 10-digit number.")
        if Customer.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("Phone number already exists.")
        return value

    # ---------------------------
    # CREATE CUSTOMER
    # ---------------------------
    def create(self, validated_data):
        # Extract monthly_income
        monthly_income = validated_data.pop('monthly_income')

        # Calculate approved_limit = 36 * monthly_income, rounded to nearest lakh
        approved_limit = round((36 * monthly_income) / 100000) * 100000

        # Save customer
        customer = Customer.objects.create(
            **validated_data,
            monthly_salary=monthly_income,
            approved_limit=approved_limit
        )
        return customer


#loans/serializers.py
class LoanEligibilityRequestSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    loan_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    interest_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    tenure = serializers.IntegerField()


class LoanEligibilityResponseSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    approval = serializers.BooleanField()
    interest_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    corrected_interest_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    tenure = serializers.IntegerField()
    monthly_installment = serializers.DecimalField(max_digits=12, decimal_places=2)

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['customer_id', 'first_name', 'last_name', 'phone_number', 'age']

class LoanViewSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer()
    is_approved = serializers.SerializerMethodField()
    monthly_installment = serializers.DecimalField(source='monthly_repayment', max_digits=12, decimal_places=2)

    class Meta:
        model = Loan
        fields = [
            'loan_id',
            'customer',
            'loan_amount',
            'interest_rate',
            'is_approved',
            'monthly_installment',
            'tenure',
        ]

    def get_is_approved(self, obj):
        # Check if a loan application exists and is approved
        if hasattr(obj, 'application') and obj.application.status == 'APPROVED':
            return True
        return False
    

class CreateLoanRequestSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    loan_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    interest_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    tenure = serializers.IntegerField()

class CreateLoanResponseSerializer(serializers.Serializer):
    loan_id = serializers.IntegerField(allow_null=True)
    customer_id = serializers.IntegerField()
    loan_approved = serializers.BooleanField()
    message = serializers.CharField()
    monthly_installment = serializers.DecimalField(max_digits=12, decimal_places=2)

