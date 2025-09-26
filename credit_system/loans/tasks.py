import os
import pandas as pd
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from loans.models import Customer, Loan, DataIngestionLog
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def load_customers_task(self, file_path=None):
    """
    Background task to load customers from Excel file
    """
    # Create ingestion log
    log = DataIngestionLog.objects.create(
        ingestion_type='CUSTOMER',
        file_name=file_path or 'customers.xlsx',
        status='STARTED'
    )
    
    try:
        # Path to Excel file
        if not file_path:
            file_path = os.path.join("data", "customer_data.xlsx")
        
        if not os.path.exists(file_path):
            error_msg = f"Excel file not found: {file_path}"
            log.status = 'FAILED'
            log.error_message = error_msg
            log.completed_at = timezone.now()
            log.save()
            logger.error(error_msg)
            return {'status': 'error', 'message': error_msg}
        
        df = pd.read_excel(file_path)
        log.total_records = len(df)
        log.save()
        
        created_count = 0
        skipped_count = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                # Handle different possible column names
                customer_id = row.get('customer_id', row.get('Customer ID'))
                first_name = row.get('first_name', row.get('First Name'))
                last_name = row.get('last_name', row.get('Last Name'))
                phone_number = int(row.get('phone_number', row.get('Phone Number')))
                monthly_salary = Decimal(str(row.get('monthly_salary', row.get('Monthly Salary'))))
                approved_limit = Decimal(str(row.get('approved_limit', row.get('Approved Limit'))))
                current_debt = Decimal(str(row.get('current_debt', row.get('Current Debt', 0))))
                
                # Check if customer already exists
                if Customer.objects.filter(phone_number=phone_number).exists():
                    skipped_count += 1
                    continue
                
                customer = Customer.objects.create(
                    first_name=first_name,
                    last_name=last_name,
                    age=int(row.get('age', row.get('Age', 25))),  # Default age if not provided
                    phone_number=phone_number,
                    monthly_salary=monthly_salary,
                    approved_limit=approved_limit,
                    current_debt=current_debt
                )
                created_count += 1
                
                # Update progress
                if created_count % 100 == 0:
                    self.update_state(
                        state='PROGRESS',
                        meta={'created': created_count, 'total': len(df)}
                    )
                    
            except Exception as e:
                errors.append(f"Row {index + 1}: {str(e)}")
                continue
        
        # Update log
        log.successful_records = created_count
        log.failed_records = len(df) - created_count - skipped_count
        log.status = 'COMPLETED'
        log.completed_at = timezone.now()
        if errors:
            log.error_details = errors[:10]  # Store first 10 errors
        log.save()
        
        result = {
            'status': 'success',
            'created': created_count,
            'skipped': skipped_count,
            'errors': len(errors)
        }
        logger.info(f"Customer loading completed: {result}")
        return result
        
    except Exception as e:
        log.status = 'FAILED'
        log.error_message = str(e)
        log.completed_at = timezone.now()
        log.save()
        logger.error(f"Customer loading failed: {str(e)}")
        raise

@shared_task(bind=True)
def load_loans_task(self, file_path=None):
    """
    Background task to load loans from Excel file
    """
    # Create ingestion log
    log = DataIngestionLog.objects.create(
        ingestion_type='LOAN',
        file_name=file_path or 'loans.xlsx',
        status='STARTED'
    )
    
    try:
        # Path to Excel file
        if not file_path:
            file_path = os.path.join("data", "loan_data.xlsx")
        
        if not os.path.exists(file_path):
            error_msg = f"Excel file not found: {file_path}"
            log.status = 'FAILED'
            log.error_message = error_msg
            log.completed_at = timezone.now()
            log.save()
            logger.error(error_msg)
            return {'status': 'error', 'message': error_msg}
        
        df = pd.read_excel(file_path)
        log.total_records = len(df)
        log.save()
        
        loans_created = 0
        customers_updated = 0
        skipped_count = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                # Handle different possible column names
                customer_id = int(row.get('customer_id', row.get('Customer ID')))
                loan_id = int(row.get('loan_id', row.get('Loan ID')))
                
                try:
                    customer = Customer.objects.get(customer_id=customer_id)
                except Customer.DoesNotExist:
                    skipped_count += 1
                    errors.append(f"Row {index + 1}: Customer {customer_id} not found")
                    continue
                
                loan_amount = Decimal(str(row.get('loan_amount', row.get('Loan Amount'))))
                tenure = int(row.get('tenure', row.get('Tenure')))
                interest_rate = Decimal(str(row.get('interest_rate', row.get('Interest Rate'))))
                
                # Use Monthly payment from Excel if available, else calculate
                monthly_payment = row.get('monthly_payment', row.get('Monthly Payment'))
                if monthly_payment and not pd.isna(monthly_payment):
                    monthly_payment = Decimal(str(monthly_payment))
                else:
                    # Standard EMI calculation
                    r = float(interest_rate) / (12 * 100)
                    n = tenure
                    principal = float(loan_amount)
                    if r == 0:
                        monthly_payment = Decimal(str(principal / n))
                    else:
                        emi = (principal * r * (1 + r) ** n) / ((1 + r) ** n - 1)
                        monthly_payment = Decimal(str(round(emi, 2)))
                
                loan = Loan.objects.create(
                    loan_id=loan_id,
                    customer=customer,
                    loan_amount=loan_amount,
                    tenure=tenure,
                    interest_rate=interest_rate,
                    monthly_repayment=monthly_payment,
                    emis_paid_on_time=int(row.get('emis_paid_on_time', row.get('EMIs Paid On Time', 0))),
                    start_date=pd.to_datetime(row.get('start_date', row.get('Date of Approval'))).date(),
                    end_date=pd.to_datetime(row.get('end_date', row.get('End Date'))).date(),
                )
                loans_created += 1
                
                # Update customer's current_debt
                customer.current_debt = sum(l.loan_amount for l in customer.loans.all())
                customer.save(update_fields=["current_debt"])
                customers_updated += 1
                
                # Update progress
                if loans_created % 50 == 0:
                    self.update_state(
                        state='PROGRESS',
                        meta={'created': loans_created, 'total': len(df)}
                    )
                    
            except Exception as e:
                errors.append(f"Row {index + 1}: {str(e)}")
                continue
        
        # Update log
        log.successful_records = loans_created
        log.failed_records = len(df) - loans_created - skipped_count
        log.status = 'COMPLETED'
        log.completed_at = timezone.now()
        if errors:
            log.error_details = errors[:10]  # Store first 10 errors
        log.save()
        
        result = {
            'status': 'success',
            'loans_created': loans_created,
            'customers_updated': customers_updated,
            'skipped': skipped_count,
            'errors': len(errors)
        }
        logger.info(f"Loan loading completed: {result}")
        return result
        
    except Exception as e:
        log.status = 'FAILED'
        log.error_message = str(e)
        log.completed_at = timezone.now()
        log.save()
        logger.error(f"Loan loading failed: {str(e)}")
        raise

@shared_task
def calculate_credit_scores_task():
    """
    Background task to recalculate credit scores for all customers
    """
    from loans.services.eligibility_service import calculate_credit_score
    from loans.models import CreditScore
    
    customers = Customer.objects.all()
    updated_count = 0
    
    for customer in customers:
        try:
            score = calculate_credit_score(customer)
            
            # Update or create credit score
            credit_score, created = CreditScore.objects.get_or_create(
                customer=customer,
                is_current=True,
                defaults={'score': score}
            )
            
            if not created:
                credit_score.score = score
                credit_score.calculation_date = timezone.now()
                credit_score.save()
            
            updated_count += 1
            
        except Exception as e:
            logger.error(f"Error calculating credit score for customer {customer.customer_id}: {str(e)}")
            continue
    
    logger.info(f"Credit scores updated for {updated_count} customers")
    return {'updated': updated_count}