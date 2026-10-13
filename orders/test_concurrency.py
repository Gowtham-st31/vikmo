from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient
from rest_framework import status
from catalogue.models import Product, Inventory
from dealers.models import Dealer
from orders.models import Order
import threading
from django.db import connection

class ConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.dealer = Dealer.objects.create(dealer_code="D-CON", name="Concurrent Dealer")
        self.product = Product.objects.create(
            sku="CONC-SKU",
            name="Concurrent Product",
            price="100.00"
        )
        self.inventory = Inventory.objects.create(product=self.product, quantity=1)
        
        self.order1 = Order.objects.create(order_number="ORD-1", dealer=self.dealer, status='DRAFT')
        self.order1.items.create(product=self.product, quantity=1, unit_price=0, line_subtotal=0, line_tax=0, line_total=0)
        
        self.order2 = Order.objects.create(order_number="ORD-2", dealer=self.dealer, status='DRAFT')
        self.order2.items.create(product=self.product, quantity=1, unit_price=0, line_subtotal=0, line_tax=0, line_total=0)

    def test_concurrent_confirms_no_oversell(self):
        
        results = []
        
        def confirm_order(order_num):
            client = APIClient()
            response = client.post(f'/api/orders/{order_num}/confirm/')
            results.append(response.status_code)
            connection.close()

        t1 = threading.Thread(target=confirm_order, args=("ORD-1",))
        t2 = threading.Thread(target=confirm_order, args=("ORD-2",))
        
        t1.start()
        t2.start()
        
        t1.join()
        t2.join()
        
        # One should succeed (200), one should fail (409)
        self.assertIn(status.HTTP_200_OK, results)
        self.assertIn(status.HTTP_409_CONFLICT, results)
        
        # Stock should be 0, not -1
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 0)

    def test_concurrent_idempotency(self):
        results = []
        key = "IDEMP-TEST-123"
        payload = {
            "dealer_id": self.dealer.id,
            "items": [{"sku": "CONC-SKU", "quantity": 1}]
        }

        def post_order():
            client = APIClient()
            response = client.post(
                '/api/orders/', 
                payload, 
                format='json',
                HTTP_IDEMPOTENCY_KEY=key
            )
            results.append(response.status_code)
            connection.close()

        threads = []
        for _ in range(10):
            t = threading.Thread(target=post_order)
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join()

        # All 10 threads should get 201 Created (the first one creates, others return the existing order)
        for status_code in results:
            self.assertEqual(status_code, status.HTTP_201_CREATED)

        # But only EXACTLY 1 order should have been created for this dealer
        self.assertEqual(Order.objects.filter(dealer=self.dealer).count(), 3)  # 2 from setUp, 1 new
