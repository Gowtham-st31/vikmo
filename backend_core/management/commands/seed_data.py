import csv
from django.core.management.base import BaseCommand
from django.conf import settings
from catalogue.models import Product, Inventory
from dealers.models import Dealer
import os

class Command(BaseCommand):
    help = 'Seed database with initial data from CSV files'

    def handle(self, *args, **options):
        data_dir = settings.DATA_DIR

        # 1. Seed Dealers
        dealers_file = os.path.join(data_dir, 'dealers.csv')
        if os.path.exists(dealers_file):
            with open(dealers_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    Dealer.objects.update_or_create(
                        dealer_code=row['dealer_code'].strip(),
                        defaults={
                            'name': row.get('name', '').strip(),
                            'city': row.get('city', '').strip() or None,
                            'phone': row.get('phone', '').strip() or None,
                            'email': row.get('email', '').strip() or None,
                            'gstin': row.get('gstin', '').strip() or None,
                            'credit_limit': row.get('credit_limit', '0.00').strip() or '0.00',
                        }
                    )
            self.stdout.write(self.style.SUCCESS('Successfully seeded dealers.'))

        # 2. Seed Catalogue
        catalogue_file = os.path.join(data_dir, 'catalogue.csv')
        if os.path.exists(catalogue_file):
            with open(catalogue_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    sku = row['sku'].strip()
                    price = row.get('price', '0.00').strip()
                    if not price:
                        price = '0.00'
                    
                    product, created = Product.objects.update_or_create(
                        sku=sku,
                        defaults={
                            'name': row.get('name', '').strip(),
                            'category': row.get('category', '').strip(),
                            'brand': row.get('brand', '').strip(),
                            'vehicle_fitment': row.get('vehicle_fitment', '').strip(),
                            'price': price,
                            'description': row.get('description', '').strip(),
                        }
                    )
                    
                    # Set starting stock only when the inventory row is created
                    if not hasattr(product, 'inventory'):
                        stock = row.get('stock', '0').strip()
                        try:
                            stock = int(stock)
                        except ValueError:
                            stock = 0
                        Inventory.objects.create(product=product, quantity=stock)

            self.stdout.write(self.style.SUCCESS('Successfully seeded catalogue and inventory.'))
