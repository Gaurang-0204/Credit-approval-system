import os
import pandas as pd
from decimal import Decimal
from django.core.management.base import BaseCommand
from loans.models import Customer, Loan
from django.utils import timezone


class Command(BaseCommand):
    help = "Load loans from Excel into the database and update Customer current_debt"

    def handle(self, *args, **kwargs):
        excel_path = os.path.join("data", "loans.xlsx")

        if not os.path.exists(excel_path):
            self.stdout.write(self.style.ERROR(f"Excel file not found: {excel_path}"))
            return

        df = pd.read_excel(excel_path)
        df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
        df.columns = df.columns.str.strip()

        loans_created = 0
        customers_updated = 0
        skipped_count = 0

        for _, row in df.iterrows():
            customer_id = int(row["customer_id"])

            try:
                customer = Customer.objects.get(customer_id=customer_id)
            except Customer.DoesNotExist:
                skipped_count += 1
                continue  # skip if customer does not exist

            loan_amount = Decimal(str(row["loan_amount"]))
            tenure = int(row["tenure"])
            interest_rate = Decimal(str(row["interest_rate"]))

            # Use Monthly payment from Excel if available, else calculate
            monthly_payment = row.get("monthly_payment")
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

            loan = Loan(
                customer=customer,
                loan_id=int(row["loan_id"]),
                loan_amount=loan_amount,
                tenure=tenure,
                interest_rate=interest_rate,
                monthly_repayment=monthly_payment,
                emis_paid_on_time=int(row.get("emis_paid_on_time", 0)),
                start_date=pd.to_datetime(row["date_of_approval"]).date(),
                end_date=pd.to_datetime(row["end_date"]).date(),
                created_at=timezone.now(),
            )
            loan.save()
            loans_created += 1

            # Update customer's current_debt
            customer.current_debt = sum(l.loan_amount for l in customer.loans.all())
            customer.save(update_fields=["current_debt"])
            customers_updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Loans created: {loans_created}, "
                f"Customers updated: {customers_updated}, "
                f"Skipped: {skipped_count}"
            )
        )
