from rest_framework import serializers
from .models import Order, OrderItem
from catalogue.models import Product
from decimal import Decimal, ROUND_HALF_UP

def get_product_price(product):
    return product.price

def compute_order_totals(items_data):
    subtotal = Decimal('0.00')
    tax_total = Decimal('0.00')
    
    for item in items_data:
        qty = Decimal(str(item['quantity']))
        unit_price = Decimal(str(item['unit_price']))
        line_subtotal = (unit_price * qty).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        line_tax = (line_subtotal * Decimal('0.18')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        line_total = line_subtotal + line_tax
        
        item['line_subtotal'] = f"{line_subtotal:.2f}"
        item['line_tax'] = f"{line_tax:.2f}"
        item['line_total'] = f"{line_total:.2f}"
        
        subtotal += line_subtotal
        tax_total += line_tax
        
    grand_total = subtotal + tax_total
    return f"{subtotal:.2f}", f"{tax_total:.2f}", f"{grand_total:.2f}"


class OrderItemInputSerializer(serializers.Serializer):
    sku = serializers.CharField(max_length=50)
    quantity = serializers.IntegerField(min_value=1)

class OrderInputSerializer(serializers.Serializer):
    dealer_id = serializers.IntegerField(required=False)
    items = OrderItemInputSerializer(many=True, allow_empty=False)

    def validate_items(self, value):
        skus = []
        for item in value:
            sku = item['sku']
            if sku in skus:
                raise serializers.ValidationError(f"Duplicate SKU {sku} in order")
            skus.append(sku)
        return value

class OrderItemOutputSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source='product.sku')
    name = serializers.CharField(source='product.name')
    
    class Meta:
        model = OrderItem
        fields = ['sku', 'name', 'quantity', 'unit_price', 'line_subtotal', 'line_tax', 'line_total']

    def to_representation(self, instance):
        # Dynamically compute for DRAFT
        if instance.order.status == 'DRAFT':
            unit_price = get_product_price(instance.product)
        else:
            unit_price = instance.unit_price

        qty = Decimal(str(instance.quantity))
        line_subtotal = (unit_price * qty).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        line_tax = (line_subtotal * Decimal('0.18')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        line_total = line_subtotal + line_tax
        
        return {
            'sku': instance.product.sku,
            'name': instance.product.name,
            'quantity': instance.quantity,
            'unit_price': f"{unit_price:.2f}",
            'line_subtotal': f"{line_subtotal:.2f}",
            'line_tax': f"{line_tax:.2f}",
            'line_total': f"{line_total:.2f}",
        }


class OrderOutputSerializer(serializers.ModelSerializer):
    items = OrderItemOutputSerializer(many=True)

    class Meta:
        model = Order
        fields = ['order_number', 'dealer_id', 'status', 'items', 'subtotal', 'tax_total', 'grand_total', 'created_at', 'updated_at']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        
        if instance.status == 'DRAFT':
            sub, tax, grand = compute_order_totals(ret['items'])
            ret['subtotal'] = sub
            ret['tax_total'] = tax
            ret['grand_total'] = grand
        else:
            ret['subtotal'] = f"{instance.subtotal:.2f}"
            ret['tax_total'] = f"{instance.tax_total:.2f}"
            ret['grand_total'] = f"{instance.grand_total:.2f}"

        return ret
