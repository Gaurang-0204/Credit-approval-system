from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from decimal import Decimal
from datetime import date, timedelta
from django.utils import timezone
from loans.models import Customer, Loan, LoanApplication, CreditScore
from .serializers import (
    CustomerRegisterSerializer, 
    LoanEligibilityRequestSerializer, 
    LoanEligibilityResponseSerializer,
    LoanViewSerializer,
    CreateLoanRequestSerializer,
    CreateLoanResponseSerializer
)
from .services.eligibility_service import evaluate_loan
from .tasks import load_customers_task, load_loans_task
import logging

logger = logging.getLogger(__name__)

@api_view(['POST'])
def register(request):
    """
    API endpoint to register a new customer
    Expected response format as per assignment
    """
    serializer = CustomerRegisterSerializer(data=request.data)
    if serializer.is_valid():
        customer = serializer.save()
        response_data = {
            "customer_id": customer.customer_id,
            "name": customer.get_full_name(),
            "age": customer.age,
            "monthly_income": float(customer.monthly_salary),
            "approved_limit": float(customer.approved_limit),
            "phone_number": str(customer.phone_number)
        }
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(["POST"])
def check_eligibility(request):
    """
    API endpoint to check loan eligibility
    Expected response format as per assignment
    """
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
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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
    Expected response format as per assignment
    """
    serializer = CreateLoanRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    
    try:
        customer = Customer.objects.get(customer_id=data["customer_id"])
    except Customer.DoesNotExist:
        return Response({"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)

    loan_amount = data["loan_amount"]
    interest_rate = data["interest_rate"]
    tenure = data["tenure"]

    approved, message, emi, credit_score = evaluate_loan_eligibility(
        customer, loan_amount, interest_rate, tenure
    )

    # Create LoanApplication
    application = LoanApplication.objects.create(
        customer=customer,
        requested_amount=loan_amount,
        requested_interest_rate=interest_rate,
        requested_tenure=tenure,
        status='APPROVED' if approved else 'REJECTED',
        monthly_installment=emi,
        credit_score_at_application=credit_score,
        rejection_message=None if approved else message,
        processed_at=timezone.now()
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

    # Response format as per assignment specification
    response_data = {
        "loan_id": loan_id,
        "customer_id": customer.customer_id,
        "loan_approved": approved,
        "message": message,
        "monthly_installment": float(emi)
    }
    
    response_serializer = CreateLoanResponseSerializer(response_data)
    return Response(response_serializer.data, status=status.HTTP_200_OK)

@api_view(["GET"])
def view_loan(request, loan_id):
    """
    API endpoint to view a specific loan
    Expected response format as per assignment
    """
    try:
        loan = Loan.objects.get(loan_id=loan_id)
    except Loan.DoesNotExist:
        return Response({"error": "Loan not found"}, status=status.HTTP_404_NOT_FOUND)

    # Check if the loan has an approved application
    loan_approved = False
    if hasattr(loan, 'application') and loan.application.status == "APPROVED":
        loan_approved = True

    response_data = {
        "loan_id": loan.loan_id,
        "customer": {
            "customer_id": loan.customer.customer_id,
            "first_name": loan.customer.first_name,
            "last_name": loan.customer.last_name,
            "phone_number": str(loan.customer.phone_number),
            "age": loan.customer.age
        },
        "loan_amount": float(loan.loan_amount),
        "interest_rate": float(loan.interest_rate),
        "loan_approved": loan_approved,
        "monthly_installment": float(loan.monthly_repayment),
        "tenure": loan.tenure
    }
    
    return Response(response_data, status=status.HTTP_200_OK)

@api_view(["GET"])
def view_loans(request, customer_id):
    """
    API endpoint to view all loans for a customer
    Expected response format as per assignment
    """
    try:
        customer = Customer.objects.get(customer_id=customer_id)
    except Customer.DoesNotExist:
        return Response({"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)

    loans = customer.loans.all()  # Related name from Loan model: loans
    response_data = []
    
    for loan in loans:
        loan_approved = False
        if hasattr(loan, 'application') and loan.application.status == "APPROVED":
            loan_approved = True
            
        response_data.append({
            "loan_id": loan.loan_id,
            "loan_amount": float(loan.loan_amount),
            "loan_approved": loan_approved,
            "interest_rate": float(loan.interest_rate),
            "monthly_installment": float(loan.monthly_repayment),
            "repayments_left": loan.repayments_left
        })
    
    return Response(response_data, status=status.HTTP_200_OK)

# Background task endpoints
@api_view(['POST'])
def ingest_customer_data(request):
    """
    API endpoint to trigger customer data ingestion as background task
    """
    file_path = request.data.get('file_path', 'data/customer_data.xlsx')
    
    try:
        task = load_customers_task.delay(file_path)
        return Response({
            'task_id': task.id,
            'status': 'Task started',
            'message': 'Customer data ingestion started in background'
        }, status=status.HTTP_202_ACCEPTED)
    except Exception as e:
        logger.error(f"Failed to start customer ingestion task: {str(e)}")
        return Response({
            'error': 'Failed to start background task',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def ingest_loan_data(request):
    """
    API endpoint to trigger loan data ingestion as background task
    """
    file_path = request.data.get('file_path', 'data/loan_data.xlsx')
    
    try:
        task = load_loans_task.delay(file_path)
        return Response({
            'task_id': task.id,
            'status': 'Task started',
            'message': 'Loan data ingestion started in background'
        }, status=status.HTTP_202_ACCEPTED)
    except Exception as e:
        logger.error(f"Failed to start loan ingestion task: {str(e)}")
        return Response({
            'error': 'Failed to start background task',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def task_status(request, task_id):
    """
    API endpoint to check background task status
    """
    from celery.result import AsyncResult
    
    task_result = AsyncResult(task_id)
    
    response_data = {
        'task_id': task_id,
        'status': task_result.status,
        'result': task_result.result
    }
    
    if task_result.status == 'PROGRESS':
        response_data['progress'] = task_result.info
    
    return Response(response_data, status=status.HTTP_200_OK)
