from django.urls import path
from .views import (
    register,
    check_eligibility,
    create_loan,
    view_loan,
    view_loans,
    ingest_customer_data,
    ingest_loan_data,
    task_status
)

urlpatterns = [
    # Main API endpoints as per assignment
    path('register/', register, name='customer-register'),
    path("check-eligibility/", check_eligibility, name="check-eligibility"),
    path("create-loan/", create_loan, name="create-loan"),
    path('view-loan/<int:loan_id>/', view_loan, name='view-loan'),
    path('view-loans/<int:customer_id>/', view_loans, name='view-loans-by-customer'),
    
    # Background task endpoints
    path('ingest-customer-data/', ingest_customer_data, name='ingest-customer-data'),
    path('ingest-loan-data/', ingest_loan_data, name='ingest-loan-data'),
    path('task-status/<str:task_id>/', task_status, name='task-status'),
]