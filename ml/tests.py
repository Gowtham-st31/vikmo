from django.test import TestCase
from rest_framework.test import APIClient
from catalogue.models import Product, Inventory

class MLTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.p1 = Product.objects.create(sku='BRK-1090', name='Test 1', price='100.00', category='Brakes')
        self.p2 = Product.objects.create(sku='FIL-1016', name='Test 2', price='200.00', category='Filters')
        self.p3 = Product.objects.create(sku='ELE-1043', name='Test 3', price='300.00', category='Electronics')
        
        Inventory.objects.create(product=self.p1, quantity=100)
        Inventory.objects.create(product=self.p2, quantity=50)
        Inventory.objects.create(product=self.p3, quantity=10)

    def test_reorder_suggestions(self):
        response = self.client.get('/api/reorder-suggestions/')
        self.assertEqual(response.status_code, 200)
        results = response.data['results']
        self.assertEqual(len(results), 40)
        
        # Verify it uses live stock
        brk = next((x for x in results if x['sku'] == 'BRK-1090'), None)
        self.assertEqual(brk['current_stock'], 100)
        
        # Change stock and verify
        inv = Inventory.objects.get(product=self.p1)
        inv.quantity = 5
        inv.save()
        
        response2 = self.client.get('/api/reorder-suggestions/')
        results2 = response2.data['results']
        brk2 = next((x for x in results2 if x['sku'] == 'BRK-1090'), None)
        self.assertEqual(brk2['current_stock'], 5)
        self.assertGreater(brk2['reorder_qty'], brk['reorder_qty'])
