from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from catalogue.models import Product, Inventory
from dealers.models import Dealer
from decimal import Decimal, ROUND_HALF_UP
import csv
import os
import math
from django.conf import settings

class OrderTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dealer = Dealer.objects.create(dealer_code="D-001", name="Test Dealer")
        self.product = Product.objects.create(
            sku="TEST-SKU",
            name="Test Product",
            price="100.00"
        )
        self.inventory = Inventory.objects.create(product=self.product, quantity=10)

    def test_create_draft_order(self):
        response = self.client.post('/api/orders/', {
            "dealer_id": self.dealer.id,
            "items": [
                {"sku": "TEST-SKU", "quantity": 2}
            ]
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'DRAFT')
        self.assertEqual(len(response.data['items']), 1)
        self.assertEqual(response.data['items'][0]['sku'], "TEST-SKU")
        self.assertEqual(response.data['items'][0]['quantity'], 2)
        # 100 * 2 = 200
        # tax = 200 * 0.18 = 36
        # total = 236
        self.assertEqual(response.data['items'][0]['line_subtotal'], "200.00")
        self.assertEqual(response.data['items'][0]['line_tax'], "36.00")
        self.assertEqual(response.data['items'][0]['line_total'], "236.00")
        self.assertEqual(response.data['subtotal'], "200.00")
        self.assertEqual(response.data['tax_total'], "36.00")
        self.assertEqual(response.data['grand_total'], "236.00")

    def test_create_order_invalid_dealer(self):
        response = self.client.post('/api/orders/', {
            "dealer_id": 9999,
            "items": [
                {"sku": "TEST-SKU", "quantity": 2}
            ]
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error']['code'], 'VALIDATION_ERROR')

    def test_create_order_invalid_product(self):
        response = self.client.post('/api/orders/', {
            "dealer_id": self.dealer.id,
            "items": [
                {"sku": "NON-EXISTENT", "quantity": 2}
            ]
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error']['code'], 'VALIDATION_ERROR')

    def test_dispatch_unknown_order_404(self):
        response = self.client.post('/api/orders/ORD-UNKNOWN/dispatch/')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['error']['code'], 'NOT_FOUND')

    def test_deliver_unknown_order_404(self):
        response = self.client.post('/api/orders/ORD-UNKNOWN/deliver/')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['error']['code'], 'NOT_FOUND')

    def test_cancel_unknown_order_404(self):
        response = self.client.post('/api/orders/ORD-UNKNOWN/cancel/')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['error']['code'], 'NOT_FOUND')

    def test_delete_order_blocked_405(self):
        r = self.client.post('/api/orders/', {
            "dealer_id": self.dealer.id,
            "items": [{"sku": "TEST-SKU", "quantity": 1}]
        }, format='json')
        self.assertEqual(r.status_code, 201)
        order_num = r.data['order_number']
        response = self.client.delete(f'/api/orders/{order_num}/')
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.data['error']['code'], 'METHOD_NOT_ALLOWED')

    def test_empty_items_validation(self):
        response = self.client.post('/api/orders/', {
            "dealer_id": self.dealer.id,
            "items": []
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['code'], 'VALIDATION_ERROR')

    def test_duplicate_product_sku_409(self):
        """Creating a product with an existing SKU must return 409 DUPLICATE."""
        response = self.client.post('/api/products/', {
            "sku": "TEST-SKU",
            "name": "Duplicate",
            "category": "Test",
            "brand": "Test",
            "vehicle_fitment": "Test",
            "price": "50.00",
            "description": "duplicate"
        }, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'DUPLICATE')

    def test_duplicate_dealer_code_409(self):
        """Creating a dealer with an existing dealer_code must return 409 DUPLICATE."""
        response = self.client.post('/api/dealers/', {
            "dealer_code": "D-001",
            "name": "Another Dealer"
        }, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'DUPLICATE')


class GSTRoundingEdgeCaseTests(TestCase):
    """Test GST rounding edge cases with prices that don't divide cleanly."""
    def setUp(self):
        self.client = APIClient()
        self.dealer = Dealer.objects.create(dealer_code="D-GST", name="GST Dealer")

    def test_gst_rounding_odd_price(self):
        """Half-up tie test: Price 729.75 * 3 = 2189.25, tax = 2189.25 * 0.18 = 394.065 -> rounds up to 394.07."""
        p = Product.objects.create(sku="GST-0001", name="Odd Price", price="729.75")
        Inventory.objects.create(product=p, quantity=100)
        
        r = self.client.post('/api/orders/', {
            "dealer_id": self.dealer.id,
            "items": [{"sku": "GST-0001", "quantity": 3}]
        }, format='json')
        self.assertEqual(r.status_code, 201)
        item = r.data['items'][0]
        
        # Assert literal expected values for the exact half-cent tie (394.065 -> 394.07)
        self.assertEqual(item['line_subtotal'], "2189.25")
        self.assertEqual(item['line_tax'], "394.07")
        self.assertEqual(item['line_total'], "2583.32")
        self.assertEqual(r.data['subtotal'], "2189.25")
        self.assertEqual(r.data['tax_total'], "394.07")
        self.assertEqual(r.data['grand_total'], "2583.32")

    def test_gst_rounding_small_price(self):
        """Price 0.99 * 1: tax = 0.99 * 0.18 = 0.1782 -> 0.18"""
        p = Product.objects.create(sku="GST-0002", name="Tiny Price", price="0.99")
        Inventory.objects.create(product=p, quantity=100)
        
        r = self.client.post('/api/orders/', {
            "dealer_id": self.dealer.id,
            "items": [{"sku": "GST-0002", "quantity": 1}]
        }, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['items'][0]['line_subtotal'], "0.99")
        self.assertEqual(r.data['items'][0]['line_tax'], "0.18")
        self.assertEqual(r.data['items'][0]['line_total'], "1.17")

    def test_gst_half_up_boundary(self):
        """Price test near whole-penny boundary: 13.89 * 0.18 = 2.5002 -> 2.50."""
        p = Product.objects.create(sku="GST-0003", name="Boundary", price="13.89")
        Inventory.objects.create(product=p, quantity=100)
        
        r = self.client.post('/api/orders/', {
            "dealer_id": self.dealer.id,
            "items": [{"sku": "GST-0003", "quantity": 1}]
        }, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['items'][0]['line_tax'], "2.50")


class ReorderFormulaTests(TestCase):
    """Hand-computed reorder tests for 3 SKUs."""
    def setUp(self):
        self.client = APIClient()
        # Create products matching the lead_times SKUs
        self.skus = ['BRK-1090', 'ELE-1043', 'OIL-1010']
        for sku in self.skus:
            p = Product.objects.create(sku=sku, name=f"Product {sku}", price="100.00", category="Test")
            Inventory.objects.create(product=p, quantity=50)

    def test_reorder_formula_matches_hand_computation(self):
        """
        Reorder formula:
          lead_time_demand = sum of forecast_units for first L weeks
          sigma = std(ddof=1) of last 12 weeks of sales
          safety_stock = ceil(1.65 * sigma * sqrt(L))
          reorder_point = lead_time_demand + safety_stock
          reorder_qty = max(0, ceil(reorder_point - current_stock))
        """
        import pandas as pd
        
        forecast_path = os.path.join(settings.BASE_DIR, 'ml', 'forecast.csv')
        forecast_df = pd.read_csv(forecast_path)
        
        lead_times_path = os.path.join(settings.DATA_DIR, 'lead_times.csv')
        lead_times_df = pd.read_csv(lead_times_path)
        
        sales_path = os.path.join(settings.DATA_DIR, 'sales_history.csv')
        sales_df = pd.read_csv(sales_path)
        sales_df['week_start'] = pd.to_datetime(sales_df['week_start'])
        
        for sku in self.skus:
            lt_row = lead_times_df[lead_times_df['sku'] == sku].iloc[0]
            L = int(lt_row['lead_time_weeks'])
            
            # Forecast for first L weeks
            sku_forecast = forecast_df[forecast_df['sku'] == sku].sort_values('week_start').head(L)
            lead_time_demand = float(sku_forecast['forecast_units'].sum())
            
            # Sigma
            sku_sales = sales_df[sales_df['sku'] == sku].sort_values('week_start', ascending=False).head(12)
            if len(sku_sales) > 1:
                sigma = float(sku_sales['units_sold'].std(ddof=1))
            else:
                sigma = 0.0
            
            safety_stock = math.ceil(1.65 * sigma * math.sqrt(L))
            reorder_point = lead_time_demand + safety_stock
            current_stock = 50  # We set it above
            reorder_qty = max(0, math.ceil(reorder_point - current_stock))
            
            # Now check the API
            response = self.client.get('/api/reorder-suggestions/')
            self.assertEqual(response.status_code, 200)
            results = response.data['results']
            
            api_result = next((r for r in results if r['sku'] == sku), None)
            self.assertIsNotNone(api_result, f"SKU {sku} not found in results")
            self.assertEqual(api_result['current_stock'], 50)
            self.assertEqual(api_result['lead_time_weeks'], L)
            self.assertAlmostEqual(api_result['lead_time_demand'], lead_time_demand, places=2)
            self.assertEqual(api_result['safety_stock'], safety_stock)
            self.assertEqual(api_result['reorder_qty'], reorder_qty)


class ForecastEndpointTests(TestCase):
    """Test that the forecast API returns exactly what's in forecast.csv."""
    def setUp(self):
        self.client = APIClient()
        # We need the products to exist for reorder-suggestions
        for sku in ['BRK-1090', 'FIL-1016', 'ELE-1043']:
            p = Product.objects.create(sku=sku, name=f"Product {sku}", price="100.00", category="Test")
            Inventory.objects.create(product=p, quantity=10)

    def test_forecast_endpoint_equals_csv(self):
        """Forecast API data must match forecast.csv exactly."""
        forecast_path = os.path.join(settings.BASE_DIR, 'ml', 'forecast.csv')
        csv_data = {}
        with open(forecast_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                sku = row['sku']
                if sku not in csv_data:
                    csv_data[sku] = []
                csv_data[sku].append({
                    "week_start": row['week_start'],
                    "forecast_units": float(row['forecast_units'])
                })
        
        for sku in ['BRK-1090', 'FIL-1016', 'ELE-1043']:
            response = self.client.get(f'/api/forecast/{sku}/')
            self.assertEqual(response.status_code, 200)
            api_forecast = response.data['forecast']
            csv_forecast = csv_data[sku]
            
            self.assertEqual(len(api_forecast), len(csv_forecast))
            for api_row, csv_row in zip(api_forecast, csv_forecast):
                self.assertEqual(api_row['week_start'], csv_row['week_start'])
                self.assertAlmostEqual(api_row['forecast_units'], csv_row['forecast_units'], places=4)

    def test_forecast_unknown_sku_404(self):
        """Unknown SKU should return 404."""
        response = self.client.get('/api/forecast/NOPE-0000/')
        self.assertEqual(response.status_code, 404)
