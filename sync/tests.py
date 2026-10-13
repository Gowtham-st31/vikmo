from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from catalogue.models import Product, Inventory
from unittest.mock import patch, MagicMock
from django.conf import settings

class SupplierSyncTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch('sync.services.requests.get')
    def test_supplier_sync_success(self, mock_get):
        mock_response = mock_get.return_value
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "sku": "SYNC-1",
                    "supplier_sku": "SUP-1",
                    "name": "Sync Product 1",
                    "category": "Accessories",
                    "brand": "BrandX",
                    "vehicle_fitment": "Universal",
                    "description": "Desc",
                    "price": "10.50",
                    "updated_at": "2026-10-10T10:00:00Z"
                }
            ],
            "next_cursor": None
        }
        
        response = self.client.post('/api/sync/supplier/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['created'], 1)
        self.assertEqual(response.data['updated'], 0)
        self.assertEqual(response.data['unchanged'], 0)
        
        # Verify product created
        prod = Product.objects.get(sku="SYNC-1")
        self.assertEqual(prod.name, "Sync Product 1")
        
        # Verify inventory initialized to 0
        inv = Inventory.objects.get(product=prod)
        self.assertEqual(inv.quantity, 0)


class SupplierOutageTests(TestCase):
    """502 SUPPLIER_UNAVAILABLE when supplier returns 502 on every attempt, nothing changed."""
    def setUp(self):
        self.client = APIClient()
        # Pre-existing product to verify nothing is changed
        self.existing = Product.objects.create(
            sku="EXIST-01", name="Existing Part", category="Brakes",
            brand="X", vehicle_fitment="Universal", price="100.00"
        )
        Inventory.objects.create(product=self.existing, quantity=10)

    @patch('sync.services.requests.get')
    def test_supplier_502_returns_supplier_unavailable(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 502
        mock_response.headers = {}
        mock_get.return_value = mock_response

        response = self.client.post('/api/sync/supplier/')
        self.assertEqual(response.status_code, 502)
        self.assertIn('SUPPLIER_UNAVAILABLE', str(response.data))

        # Nothing should have changed
        self.existing.refresh_from_db()
        self.assertEqual(self.existing.name, "Existing Part")
        inv = Inventory.objects.get(product=self.existing)
        self.assertEqual(inv.quantity, 10)


class DuplicateSkuTests(TestCase):
    """When same SKU appears twice in the feed, the one with latest updated_at wins."""
    def setUp(self):
        self.client = APIClient()

    @patch('sync.services.requests.get')
    def test_duplicate_sku_latest_wins(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "sku": "DUP-01", "supplier_sku": "SUP-A",
                    "name": "Old Name", "category": "Brakes", "brand": "X",
                    "vehicle_fitment": "Universal", "description": "Old",
                    "price": "50.00", "updated_at": "2026-10-01T10:00:00Z"
                },
                {
                    "sku": "DUP-01", "supplier_sku": "SUP-B",
                    "name": "New Name", "category": "Brakes", "brand": "Y",
                    "vehicle_fitment": "Universal", "description": "New",
                    "price": "75.00", "updated_at": "2026-10-05T10:00:00Z"
                },
            ],
            "next_cursor": None
        }
        mock_get.return_value = mock_response

        response = self.client.post('/api/sync/supplier/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created'], 1)

        prod = Product.objects.get(sku="DUP-01")
        self.assertEqual(prod.name, "New Name")
        self.assertEqual(str(prod.price), "75.00")


class RejectedItemTests(TestCase):
    """Items with missing sku, bad price, or missing updated_at are rejected, not crashed."""
    def setUp(self):
        self.client = APIClient()

    @patch('sync.services.requests.get')
    def test_rejected_items(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "sku": "", "supplier_sku": "SUP-EMPTY",
                    "name": "Empty SKU", "category": "Brakes", "brand": "X",
                    "vehicle_fitment": "Universal", "description": "Bad",
                    "price": "10.00", "updated_at": "2026-10-01T10:00:00Z"
                },
                {
                    "sku": "BAD-PRICE", "supplier_sku": "SUP-BP",
                    "name": "Bad Price", "category": "Brakes", "brand": "X",
                    "vehicle_fitment": "Universal", "description": "Bad",
                    "price": "-5.00", "updated_at": "2026-10-01T10:00:00Z"
                },
                {
                    "sku": "NO-DATE", "supplier_sku": "SUP-ND",
                    "name": "No Date", "category": "Brakes", "brand": "X",
                    "vehicle_fitment": "Universal", "description": "Missing updated_at",
                    "price": "20.00"
                },
                {
                    "sku": "GOOD-01", "supplier_sku": "SUP-GOOD",
                    "name": "Good Product", "category": "Brakes", "brand": "X",
                    "vehicle_fitment": "Universal", "description": "OK",
                    "price": "30.00", "updated_at": "2026-10-05T10:00:00Z"
                },
            ],
            "next_cursor": None
        }
        mock_get.return_value = mock_response

        response = self.client.post('/api/sync/supplier/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created'], 1)
        self.assertEqual(len(response.data['rejected']), 3)

        Product.objects.get(sku="GOOD-01")
        self.assertFalse(Product.objects.filter(sku="BAD-PRICE").exists())
        self.assertFalse(Product.objects.filter(sku="NO-DATE").exists())

    @patch('sync.services.requests.get')
    def test_integer_price_accepted(self, mock_get):
        """Integer-looking price '500' should be accepted as valid."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "sku": "INT-PRICE", "supplier_sku": "SUP-IP",
                    "name": "Integer Price Part", "category": "Brakes", "brand": "X",
                    "vehicle_fitment": "Universal", "description": "OK",
                    "price": "500", "updated_at": "2026-10-05T10:00:00Z"
                },
            ],
            "next_cursor": None
        }
        mock_get.return_value = mock_response

        response = self.client.post('/api/sync/supplier/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created'], 1)
        prod = Product.objects.get(sku="INT-PRICE")
        self.assertEqual(str(prod.price), "500.00")


class IdempotentSecondRunTests(TestCase):
    """Running sync again on unchanged feed reports created=0, updated=0."""
    def setUp(self):
        self.client = APIClient()

    @patch('sync.services.requests.get')
    def test_second_run_idempotent(self, mock_get):
        feed = {
            "items": [
                {
                    "sku": "IDEM-01", "supplier_sku": "SUP-I1",
                    "name": "Idem Product", "category": "Brakes", "brand": "X",
                    "vehicle_fitment": "Universal", "description": "Desc",
                    "price": "25.50", "updated_at": "2026-10-05T10:00:00Z"
                },
            ],
            "next_cursor": None
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = feed
        mock_get.return_value = mock_response

        # First run
        r1 = self.client.post('/api/sync/supplier/')
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.data['created'], 1)

        # Second run with same data
        r2 = self.client.post('/api/sync/supplier/')
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.data['created'], 0)
        self.assertEqual(r2.data['updated'], 0)
        self.assertEqual(r2.data['unchanged'], 1)


class RetryAfterParsingTests(TestCase):
    """parse_retry_after safely defaults non-integers, invalid, or negative values to 1 second."""
    def test_parse_retry_after_valid_integer(self):
        from sync.services import parse_retry_after
        self.assertEqual(parse_retry_after("5"), 5)
        self.assertEqual(parse_retry_after(10), 10)

    def test_parse_retry_after_non_integer_defaults_to_1(self):
        from sync.services import parse_retry_after
        self.assertEqual(parse_retry_after("invalid"), 1)
        self.assertEqual(parse_retry_after("Wed, 21 Oct 2026 07:28:00 GMT"), 1)
        self.assertEqual(parse_retry_after(None), 1)
        self.assertEqual(parse_retry_after(""), 1)
        self.assertEqual(parse_retry_after("-5"), 1)
        self.assertEqual(parse_retry_after(0), 1)

    @patch('sync.services.time.sleep')
    @patch('sync.services.requests.get')
    def test_sync_handles_non_integer_retry_after_header(self, mock_get, mock_sleep):
        """During HTTP 429, a non-integer Retry-After header does not crash and sleeps 1s."""
        client = APIClient()
        r_429 = MagicMock()
        r_429.status_code = 429
        r_429.headers = {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}

        r_200 = MagicMock()
        r_200.status_code = 200
        r_200.json.return_value = {"items": [], "next_cursor": None}

        mock_get.side_effect = [r_429, r_200]

        res = client.post('/api/sync/supplier/')
        self.assertEqual(res.status_code, 200)
        mock_sleep.assert_called_with(1)

