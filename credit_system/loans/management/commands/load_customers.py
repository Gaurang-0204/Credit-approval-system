import os
import pandas as pd
from decimal import Decimal
from django.core.management.base import BaseCommand
from loans.models import Customer


class Command(BaseCommand):
    help = "Load customers from Excel into the database"

    def handle(self, *args, **kwargs):
        # Path to Excel file
        excel_path = os.path.join("data", "customers.xlsx")

        if not os.path.exists(excel_path):
            self.stdout.write(self.style.ERROR(f"Excel file not found: {excel_path}"))
            return

        df = pd.read_excel(excel_path)

        created_count = 0
        skipped_count = 0

        for _, row in df.iterrows():
            phone_number = int(row["Phone Number"])

            if Customer.objects.filter(phone_number=phone_number).exists():
                skipped_count += 1
                continue

            customer = Customer(
                first_name=row["First Name"],
                last_name=row["Last Name"],
                age=int(row["Age"]),
                phone_number=phone_number,
                monthly_salary=Decimal(str(row["Monthly Salary"])),
                current_debt=Decimal(str(row.get("current_debt", 0))),
            )
            customer.save()
            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Loaded {created_count} customers, skipped {skipped_count} (already exist)."
            )
        )
