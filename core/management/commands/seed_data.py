import csv
from django.core.management.base import BaseCommand
from django.conf import settings
from catalogue.models import Product, Inventory
from dealers.models import Dealer
import os
from django.db import transaction

class Command(BaseCommand):
    help = 'Seed database with initial data from CSV files'

    def handle(self, *args, **options):
        data_dir = settings.DATA_DIR

        # 1. Seed Dealers
        dealers_file = os.path.join(data_dir, 'dealers.csv')
        if os.path.exists(dealers_file):
            with open(dealers_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                with transaction.atomic():
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
                
                products_to_create = []
                inventory_data = {}
                
                for row in reader:
                    sku = row['sku'].strip()
                    price = row.get('price', '0.00').strip()
                    if not price:
                        price = '0.00'
                    
                    products_to_create.append(
                        Product(
                            sku=sku,
                            name=row.get('name', '').strip(),
                            category=row.get('category', '').strip(),
                            brand=row.get('brand', '').strip(),
                            vehicle_fitment=row.get('vehicle_fitment', '').strip(),
                            price=price,
                            description=row.get('description', '').strip()
                        )
                    )
                    
                    stock = row.get('stock', '0').strip()
                    try:
                        stock = int(stock)
                    except ValueError:
                        stock = 0
                    inventory_data[sku] = stock

                # Bulk insert ignoring duplicates
                Product.objects.bulk_create(products_to_create, ignore_conflicts=True)
                
                # Fetch created products to map IDs for inventory
                created_products = Product.objects.in_bulk(field_name='sku')
                
                inventory_to_create = []
                for sku, stock in inventory_data.items():
                    if sku in created_products:
                        inventory_to_create.append(Inventory(product=created_products[sku], quantity=stock))
                
                Inventory.objects.bulk_create(inventory_to_create, ignore_conflicts=True)

            self.stdout.write(self.style.SUCCESS('Successfully seeded catalogue and inventory.'))
