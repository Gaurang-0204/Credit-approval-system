from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .serializers import CustomerRegisterSerializer,LoanEligibilityRequestSerializer, LoanEligibilityResponseSerializer,LoanViewSerializer
from .services.eligibility_service import evaluate_loan
from .models import Customer

@api_view(['POST'])
def customer_register(request):
    serializer = CustomerRegisterSerializer(data=request.data)
    if serializer.is_valid():
        customer = serializer.save()
        response_data = {
            "customer_id": customer.customer_id,
            "name": customer.get_full_name(),
            "age": customer.age,
            "monthly_income": customer.monthly_salary,
            "approved_limit": customer.approved_limit,
            "phone_number": customer.phone_number
        }
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def check_eligibility(request):
    serializer = LoanEligibilityRequestSerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.validated_data
        try:
            customer = Customer.objects.get(customer_id=data['customer_id'])
        except Customer.DoesNotExist:
            return Response({"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)

        approved, credit_score, interest_rate, corrected_rate, emi = evaluate_loan(
            customer,
            data['loan_amount'],
            data['interest_rate'],
            data['tenure']
        )

        response_data = {
            "customer_id": customer.customer_id,
    "approval": approved,
    "interest_rate": float(interest_rate),
    "corrected_interest_rate": float(corrected_rate) if corrected_rate else float(interest_rate),
    "tenure": data['tenure'],
    "monthly_installment": float(emi),
        }

        response_serializer = LoanEligibilityResponseSerializer(response_data)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from decimal import Decimal
from datetime import date, timedelta

from loans.models import Customer, Loan, LoanApplication, CreditScore


def evaluate_loan_eligibility(customer, loan_amount, interest_rate, tenure):
    """
    Evaluate if the loan can be approved based on:
    - Customer credit score
    - EMI affordability
    - Approved limit
    """
    # Fetch latest credit score
    credit_score_obj = customer.credit_scores.filter(is_current=True).first()
    credit_score = credit_score_obj.score if credit_score_obj else 50  # default if not present

    # Calculate monthly EMI
    principal = float(loan_amount)
    r = float(interest_rate) / (12 * 100)
    n = tenure

    if r == 0:
        emi = principal / n
    else:
        emi = (principal * r * (1 + r) ** n) / ((1 + r) ** n - 1)

    # Check EMI affordability (<=50% of salary)
    if emi > float(customer.monthly_salary) * 0.5:
        return False, "EMI exceeds 50% of monthly income", Decimal(str(emi)), credit_score

    # Check approved credit limit
    if (customer.get_current_loans_sum() + loan_amount) > customer.approved_limit:
        return False, "Exceeds approved credit limit", Decimal(str(emi)), credit_score

    # Check minimal credit score threshold
    if credit_score < 50:
        return False, "Credit score too low", Decimal(str(emi)), credit_score

    return True, "Loan approved", Decimal(str(round(emi, 2))), credit_score


@api_view(["POST"])
def create_loan(request):
    """
    Endpoint: /create-loan
    Processes a new loan based on eligibility
    """
    data = request.data
    required_fields = ["customer_id", "loan_amount", "interest_rate", "tenure"]
    for field in required_fields:
        if field not in data:
            return Response({"error": f"{field} is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        customer = Customer.objects.get(customer_id=data["customer_id"])
    except Customer.DoesNotExist:
        return Response({"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)

    loan_amount = Decimal(str(data["loan_amount"]))
    interest_rate = Decimal(str(data["interest_rate"]))
    tenure = int(data["tenure"])

    approved, message, emi, credit_score = evaluate_loan_eligibility(customer, loan_amount, interest_rate, tenure)

    # Create LoanApplication
    application = LoanApplication.objects.create(
        customer=customer,
        requested_amount=loan_amount,
        requested_interest_rate=interest_rate,
        requested_tenure=tenure,
        status='APPROVED' if approved else 'REJECTED',
        monthly_installment=emi,
        credit_score_at_application=credit_score,
        rejection_message=None if approved else message
    )

    loan_id = None
    if approved:
        start_date = date.today()
        end_date = start_date + timedelta(days=30 * tenure)
        loan = Loan.objects.create(
            customer=customer,
            loan_amount=loan_amount,
            interest_rate=interest_rate,
            tenure=tenure,
            start_date=start_date,
            end_date=end_date,
            monthly_repayment=emi
        )
        application.loan = loan
        application.approved_amount = loan_amount
        application.approved_interest_rate = interest_rate
        application.save()
        loan_id = loan.loan_id

    response_data = {
        "loan_id": loan_id,
        "customer_id": customer.customer_id,
        "loan_approved": approved,
        "message": message,
        "monthly_installment": float(emi)
    }

    return Response(response_data, status=status.HTTP_200_OK if approved else status.HTTP_400_BAD_REQUEST)




@api_view(["GET"])
def view_loan(request, loan_id):
    try:
        loan = Loan.objects.get(loan_id=loan_id)
    except Loan.DoesNotExist:
        return Response({"error": "Loan not found"}, status=status.HTTP_404_NOT_FOUND)

    # Check if the loan has an approved application
    loan_approved = False
    interest_rate = float(loan.interest_rate)
    if hasattr(loan, 'application') and loan.application.status == "APPROVED":
        loan_approved = True
        interest_rate = float(loan.application.approved_interest_rate or loan.interest_rate)

    response_data = {
        "loan_id": loan.loan_id,
        "customer": {
            "customer_id": loan.customer.customer_id,
            "first_name": loan.customer.first_name,
            "last_name": loan.customer.last_name,
            "phone_number": loan.customer.phone_number,
            "age": loan.customer.age
        },
        "loan_amount": float(loan.loan_amount),
        "interest_rate": interest_rate,
        "loan_approved": loan_approved,
        "monthly_installment": float(loan.monthly_repayment),
        "tenure": loan.tenure
    }

    return Response(response_data, status=status.HTTP_200_OK)


@api_view(["GET"])
def view_loans_by_customer(request, customer_id):
    try:
        customer = Customer.objects.get(customer_id=customer_id)
    except Customer.DoesNotExist:
        return Response({"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)

    loans = customer.loans.all()  # Related name from Loan model: loans
    response_data = []

    for loan in loans:
        response_data.append({
            "loan_id": loan.loan_id,
            "loan_amount": float(loan.loan_amount),
            "loan_approved": True if hasattr(loan, 'application') and loan.application.status == "APPROVED" else False,
            "interest_rate": float(loan.interest_rate),
            "monthly_installment": float(loan.monthly_repayment),
            "repayments_left": loan.repayments_left
        })

    return Response(response_data, status=status.HTTP_200_OK)