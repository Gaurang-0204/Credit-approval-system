import os
import pandas as pd
from decimal import Decimal
from django.core.management.base import BaseCommand
from loans.tasks import load_loans_task

class Command(BaseCommand):
    help = "Load loans from Excel into the database using background tasks"

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='data/loan_data.xlsx',
            help='Path to the Excel file containing loan data'
        )
        parser.add_argument(
            '--sync',
            action='store_true',
            help='Run synchronously instead of as background task'
        )

    def handle(self, *args, **kwargs):
        file_path = kwargs['file']
        sync = kwargs['sync']
        
        if sync:
            # Run synchronously for development/testing
            result = load_loans_task(file_path)
            if result['status'] == 'success':
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Loaded {result['loans_created']} loans, "
                        f"updated {result['customers_updated']} customers, "
                        f"skipped {result['skipped']}, "
                        f"errors: {result['errors']}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"Failed to load loans: {result['message']}")
                )
        else:
            # Run as background task
            task = load_loans_task.delay(file_path)
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Loan loading task started with ID: {task.id}"
                )
            )