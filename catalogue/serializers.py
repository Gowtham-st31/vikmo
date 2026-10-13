from rest_framework import serializers
from .models import Product, Inventory

class ProductSerializer(serializers.ModelSerializer):
    stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['sku', 'name', 'category', 'brand', 'vehicle_fitment', 'price', 'stock', 'description']
        # Disable DRF's auto-generated UniqueValidator on sku so we can
        # raise 409 DUPLICATE ourselves in the view instead of 400.
        extra_kwargs = {
            'sku': {'validators': []},
        }

    def get_stock(self, obj):
        if hasattr(obj, 'inventory'):
            return obj.inventory.quantity
        return 0

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0.")
        return value

class InventoryUpdateSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(required=False, allow_blank=True)
