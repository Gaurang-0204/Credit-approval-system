from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from datetime import date


class Customer(models.Model):
    """
    Customer model to store customer information
    """
    customer_id = models.AutoField(primary_key=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    age = models.IntegerField(
        validators=[MinValueValidator(18), MaxValueValidator(120)]
    )
    phone_number = models.BigIntegerField(
        validators=[MinValueValidator(1000000000), MaxValueValidator(9999999999)],
        unique=True
    )
    monthly_salary = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    approved_limit = models.DecimalField(max_digits=12, decimal_places=2)
    current_debt = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'customers'
        indexes = [
            models.Index(fields=['customer_id']),
            models.Index(fields=['phone_number']),
        ]

    def save(self, *args, **kwargs):
        """Auto-calculate approved_limit if not set"""
        if not self.approved_limit:
            limit = 36 * self.monthly_salary
            self.approved_limit = round(limit / 100000) * 100000  # nearest lakh
        super().save(*args, **kwargs)

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_current_loans_sum(self):
        active_loans = [loan for loan in self.loans.all() if loan.repayments_left > 0]
        return sum(loan.loan_amount for loan in active_loans)

    def get_current_emis_sum(self):
        active_loans = [loan for loan in self.loans.all() if loan.repayments_left > 0]
        return sum(loan.monthly_repayment for loan in active_loans)

    def __str__(self):
        return f"Customer {self.customer_id}: {self.get_full_name()}"


class Loan(models.Model):
    """
    Loan model to store loan information
    """
    loan_id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name='loans'
    )
    loan_amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('1000.00'))]
    )
    tenure = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(600)],  # months
        help_text="Loan tenure in months"
    )
    interest_rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('50.00'))],
        help_text="Annual interest rate in percentage"
    )
    monthly_repayment = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Monthly EMI amount"
    )
    emis_paid_on_time = models.IntegerField(
        default=0, validators=[MinValueValidator(0)]
    )
    start_date = models.DateField()
    end_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'loans'
        indexes = [
            models.Index(fields=['loan_id']),
            models.Index(fields=['customer', 'start_date']),
            models.Index(fields=['start_date', 'end_date']),
        ]

    def save(self, *args, **kwargs):
        if not self.monthly_repayment:
            self.monthly_repayment = self.calculate_emi()
        super().save(*args, **kwargs)

    def calculate_emi(self):
        """Standard EMI formula"""
        principal = float(self.loan_amount)
        annual_rate = float(self.interest_rate)
        n = self.tenure
        r = annual_rate / (12 * 100)  # monthly rate

        if r == 0:
            return Decimal(str(principal / n))

        emi = (principal * r * (1 + r) ** n) / ((1 + r) ** n - 1)
        return Decimal(str(round(emi, 2)))

    @property
    def repayments_left(self):
        today = date.today()
        if today >= self.end_date:
            return 0
        months_passed = (today.year - self.start_date.year) * 12 + (today.month - self.start_date.month)
        if months_passed < 0:
            return self.tenure
        return max(0, self.tenure - months_passed)

    @property
    def is_active(self):
        return self.repayments_left > 0

    @property
    def total_amount_payable(self):
        return self.monthly_repayment * self.tenure

    @property
    def total_interest(self):
        return self.total_amount_payable - self.loan_amount

    @property
    def amount_paid_so_far(self):
        emis_completed = self.tenure - self.repayments_left
        return self.monthly_repayment * emis_completed

    @property
    def remaining_amount(self):
        return self.monthly_repayment * self.repayments_left

    def __str__(self):
        return f"Loan {self.loan_id}: {self.customer.get_full_name()} - ₹{self.loan_amount}"


class CreditScore(models.Model):
    """
    Cached credit scores for customers
    """
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name='credit_scores'
    )
    score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    past_loans_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    loan_count_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    current_year_activity_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    loan_volume_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    calculation_date = models.DateTimeField(auto_now_add=True)
    is_current = models.BooleanField(default=True)

    class Meta:
        db_table = 'credit_scores'
        indexes = [
            models.Index(fields=['customer', 'is_current']),
            models.Index(fields=['calculation_date']),
        ]
        unique_together = ['customer', 'is_current']

    def save(self, *args, **kwargs):
        if self.is_current:
            CreditScore.objects.filter(
                customer=self.customer, is_current=True
            ).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Credit Score {self.score}/100 for {self.customer.get_full_name()}"


class LoanApplication(models.Model):
    """
    Loan applications (approved/rejected)
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    REJECTION_REASONS = [
        ('LOW_CREDIT_SCORE', 'Credit score too low'),
        ('HIGH_EMI_RATIO', 'EMI exceeds 50% of monthly income'),
        ('INSUFFICIENT_INCOME', 'Insufficient monthly income'),
        ('OVER_APPROVED_LIMIT', 'Exceeds approved credit limit'),
        ('HIGH_INTEREST_REQUIRED', 'Interest rate too low for credit score'),
    ]

    application_id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='loan_applications')
    loan = models.OneToOneField(
        'Loan', on_delete=models.CASCADE, null=True, blank=True, related_name='application'
    )

    requested_amount = models.DecimalField(max_digits=12, decimal_places=2)
    requested_interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    requested_tenure = models.IntegerField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    approved_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    approved_interest_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    corrected_interest_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    monthly_installment = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    rejection_reason = models.CharField(max_length=50, choices=REJECTION_REASONS, null=True, blank=True)
    rejection_message = models.TextField(null=True, blank=True)

    credit_score_at_application = models.IntegerField(null=True, blank=True)

    applied_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'loan_applications'
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['applied_at']),
            models.Index(fields=['status', 'processed_at']),
        ]

    def __str__(self):
        return f"Application {self.application_id}: {self.customer.get_full_name()} - {self.status}"


class DataIngestionLog(models.Model):
    """
    Logs for data ingestion from Excel files
    """
    INGESTION_TYPES = [
        ('CUSTOMER', 'Customer Data'),
        ('LOAN', 'Loan Data'),
    ]
    STATUS_CHOICES = [
        ('STARTED', 'Started'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    log_id = models.AutoField(primary_key=True)
    ingestion_type = models.CharField(max_length=20, choices=INGESTION_TYPES)
    file_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='STARTED')

    total_records = models.IntegerField(default=0)
    successful_records = models.IntegerField(default=0)
    failed_records = models.IntegerField(default=0)

    error_message = models.TextField(null=True, blank=True)
    error_details = models.JSONField(null=True, blank=True)

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'data_ingestion_logs'
        indexes = [
            models.Index(fields=['ingestion_type', 'status']),
            models.Index(fields=['started_at']),
        ]

    def __str__(self):
        return f"Ingestion {self.log_id}: {self.ingestion_type} - {self.status}"
