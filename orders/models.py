from django.db import models
from catalogue.models import Product
from dealers.models import Dealer

class Order(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'DRAFT'),
        ('CONFIRMED', 'CONFIRMED'),
        ('DISPATCHED', 'DISPATCHED'),
        ('DELIVERED', 'DELIVERED'),
        ('CANCELLED', 'CANCELLED'),
    ]

    order_number = models.CharField(max_length=50, primary_key=True)
    dealer = models.ForeignKey(Dealer, on_delete=models.PROTECT, related_name='orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    tax_total = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='+')
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    line_subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    line_tax = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['order', 'product'], name='unique_order_product'),
            models.CheckConstraint(check=models.Q(quantity__gte=1), name='orderitem_quantity_gte_1')
        ]

class DailySequence(models.Model):
    date = models.DateField(primary_key=True)
    last_value = models.IntegerField(default=0)

class IdempotencyRecord(models.Model):
    key = models.CharField(max_length=255, primary_key=True)
    request_hash = models.CharField(max_length=64)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
