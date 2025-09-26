from django.urls import path
from .views import customer_register,check_eligibility,create_loan,view_loan,view_loans_by_customer

urlpatterns = [
    path('register/', customer_register, name='customer-register'),
    path("check-eligibility/", check_eligibility, name="check-eligibility"),
    path("create-loan/", create_loan, name="create-loan"),
    path('view-loan/<int:loan_id>/', view_loan, name='view-loan'),
    path('view-loans/<int:customer_id>/', view_loans_by_customer, name='view-loans-by-customer'),
]
