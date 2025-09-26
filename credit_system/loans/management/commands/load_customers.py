import os
import pandas as pd
from decimal import Decimal
from django.core.management.base import BaseCommand
from loans.tasks import load_customers_task

class Command(BaseCommand):
    help = "Load customers from Excel into the database using background tasks"

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='data/customer_data.xlsx',
            help='Path to the Excel file containing customer data'
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
            result = load_customers_task(file_path)
            if result['status'] == 'success':
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Loaded {result['created']} customers, "
                        f"skipped {result['skipped']} (already exist), "
                        f"errors: {result['errors']}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"Failed to load customers: {result['message']}")
                )
        else:
            # Run as background task
            task = load_customers_task.delay(file_path)
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Customer loading task started with ID: {task.id}"
                )
            )