from django.db import models

class Product(models.Model):
    sku = models.CharField(max_length=50, primary_key=True)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    brand = models.CharField(max_length=100)
    vehicle_fitment = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.sku} - {self.name}"

class Inventory(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='inventory')
    quantity = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(check=models.Q(quantity__gte=0), name='inventory_quantity_gte_0')
        ]

    def __str__(self):
        return f"{self.product.sku}: {self.quantity}"
