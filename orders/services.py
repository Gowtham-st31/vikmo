import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction, IntegrityError
from django.utils import timezone
from zoneinfo import ZoneInfo
from rest_framework.exceptions import APIException, NotFound
from .models import Order, OrderItem, DailySequence, IdempotencyRecord
from catalogue.models import Product, Inventory
from dealers.models import Dealer

IST = ZoneInfo('Asia/Kolkata')

class InvalidTransition(APIException):
    status_code = 409
    default_code = 'INVALID_TRANSITION'
    default_detail = 'Invalid status transition.'

class OrderLocked(APIException):
    status_code = 409
    default_code = 'ORDER_LOCKED'
    default_detail = 'Order is locked and cannot be edited.'

class InsufficientStock(APIException):
    status_code = 409
    default_code = 'INSUFFICIENT_STOCK'

    def __init__(self, details):
        self.custom_code = "INSUFFICIENT_STOCK"
        self.custom_details = details
        
        msgs = []
        for d in details:
            msgs.append(f"Insufficient stock for {d['name']}. Available: {d['available']}, Requested: {d['requested']}")
        
        self.custom_message = " ".join(msgs)
        super().__init__(self.custom_message)

def generate_order_number():
    today = timezone.now().astimezone(IST).date()
    
    try:
        DailySequence.objects.get_or_create(date=today, defaults={'last_value': 0})
    except IntegrityError:
        pass

    seq = DailySequence.objects.select_for_update().get(date=today)
    seq.last_value += 1
    seq.save()
    
    date_str = today.strftime('%Y%m%d')
    seq_str = f"{seq.last_value:04d}"
    return f"ORD-{date_str}-{seq_str}"

def create_draft_order(dealer_id, items_data, idempotency_key=None, request_body=None):
    try:
        dealer = Dealer.objects.get(id=dealer_id)
    except Dealer.DoesNotExist:
        from rest_framework.exceptions import ValidationError
        class DealerValidationError(ValidationError):
            custom_code = "VALIDATION_ERROR"
        raise DealerValidationError("Dealer not found.")

    skus = [item['sku'] for item in items_data]
    products = Product.objects.filter(sku__in=skus)
    product_map = {p.sku: p for p in products}

    if len(product_map) != len(skus):
        missing = set(skus) - set(product_map.keys())
        from rest_framework.exceptions import ValidationError
        class ProductValidationError(ValidationError):
            custom_code = "VALIDATION_ERROR"
        raise ProductValidationError(f"Products not found: {', '.join(missing)}")

    request_hash = ""
    if request_body is not None:
        request_hash = hashlib.sha256(json.dumps(request_body, sort_keys=True).encode('utf-8')).hexdigest()

    with transaction.atomic():
        if idempotency_key:
            record, created = IdempotencyRecord.objects.get_or_create(
                key=idempotency_key,
                defaults={'request_hash': request_hash}
            )
            if not created:
                if record.request_hash != request_hash:
                    class IdempotencyException(APIException):
                        status_code = 409
                        custom_code = "IDEMPOTENCY_CONFLICT"
                        default_detail = "Idempotency conflict"
                    raise IdempotencyException()
                
                if record.order:
                    return record.order
                else:
                    class DuplicateRequest(APIException):
                        status_code = 409
                        custom_code = "IDEMPOTENCY_CONFLICT"
                        default_detail = "Duplicate request being processed."
                    raise DuplicateRequest()

        order_number = generate_order_number()
        order = Order.objects.create(
            order_number=order_number,
            dealer=dealer,
            status='DRAFT'
        )

        order_items = []
        for item in items_data:
            order_items.append(
                OrderItem(
                    order=order,
                    product=product_map[item['sku']],
                    quantity=item['quantity'],
                    unit_price=0,
                    line_subtotal=0,
                    line_tax=0,
                    line_total=0
                )
            )
        
        OrderItem.objects.bulk_create(order_items)

        if idempotency_key:
            record.order = order
            record.save()

    return order

def update_draft_order(order_number, items_data):
    with transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(order_number=order_number)
        except Order.DoesNotExist:
            raise NotFound()

        if order.status != 'DRAFT':
            raise OrderLocked()

        skus = [item['sku'] for item in items_data]
        products = Product.objects.filter(sku__in=skus)
        product_map = {p.sku: p for p in products}

        if len(product_map) != len(skus):
            missing = set(skus) - set(product_map.keys())
            from rest_framework.exceptions import ValidationError
            class ProductValidationError(ValidationError):
                custom_code = "VALIDATION_ERROR"
            raise ProductValidationError(f"Products not found: {', '.join(missing)}")

        order.items.all().delete()
        
        order_items = []
        for item in items_data:
            order_items.append(
                OrderItem(
                    order=order,
                    product=product_map[item['sku']],
                    quantity=item['quantity'],
                    unit_price=0,
                    line_subtotal=0,
                    line_tax=0,
                    line_total=0
                )
            )
        
        OrderItem.objects.bulk_create(order_items)
        return order


def _compute_exact_totals(order):
    subtotal = Decimal('0.00')
    tax_total = Decimal('0.00')

    items = order.items.select_related('product').all()
    for item in items:
        unit_price = item.product.price
        qty = Decimal(str(item.quantity))
        
        line_subtotal = (unit_price * qty).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        line_tax = (line_subtotal * Decimal('0.18')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        line_total = line_subtotal + line_tax
        
        item.unit_price = unit_price
        item.line_subtotal = line_subtotal
        item.line_tax = line_tax
        item.line_total = line_total
        item.save()

        subtotal += line_subtotal
        tax_total += line_tax
        
    order.subtotal = subtotal
    order.tax_total = tax_total
    order.grand_total = subtotal + tax_total
    order.save()


def confirm_order(order_number):
    with transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(order_number=order_number)
        except Order.DoesNotExist:
            raise NotFound()
            
        if order.status != 'DRAFT':
            raise InvalidTransition()

        items = list(order.items.select_related('product').all())
        skus_needed = sorted([item.product.sku for item in items])
        
        inventories = list(Inventory.objects.select_for_update().filter(product__sku__in=skus_needed).order_by('product__sku'))
        inv_map = {inv.product_id: inv for inv in inventories}
        
        short_details = []
        for item in items:
            inv = inv_map.get(item.product_id)
            if not inv or inv.quantity < item.quantity:
                short_details.append({
                    "sku": item.product.sku,
                    "name": item.product.name,
                    "requested": item.quantity,
                    "available": inv.quantity if inv else 0
                })

        if short_details:
            raise InsufficientStock(short_details)

        # Deduct stock
        for item in items:
            inv = inv_map[item.product_id]
            inv.quantity -= item.quantity
            inv.save()

        _compute_exact_totals(order)
        order.status = 'CONFIRMED'
        order.save()
        return order


def dispatch_order(order_number):
    with transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(order_number=order_number)
        except Order.DoesNotExist:
            raise NotFound()
        if order.status != 'CONFIRMED':
            raise InvalidTransition()
        order.status = 'DISPATCHED'
        order.save()
        return order


def deliver_order(order_number):
    with transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(order_number=order_number)
        except Order.DoesNotExist:
            raise NotFound()
        if order.status != 'DISPATCHED':
            raise InvalidTransition()
        order.status = 'DELIVERED'
        order.save()
        return order


def cancel_order(order_number):
    with transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(order_number=order_number)
        except Order.DoesNotExist:
            raise NotFound()
        
        if order.status == 'DRAFT':
            order.status = 'CANCELLED'
            order.save()
            return order
        elif order.status == 'CONFIRMED':
            # Restore stock
            items = list(order.items.select_related('product').all())
            skus = sorted([item.product.sku for item in items])
            inventories = list(Inventory.objects.select_for_update().filter(product__sku__in=skus).order_by('product__sku'))
            inv_map = {inv.product_id: inv for inv in inventories}
            
            for item in items:
                inv = inv_map.get(item.product_id)
                if inv:
                    inv.quantity += item.quantity
                    inv.save()
                    
            order.status = 'CANCELLED'
            order.save()
            return order
        else:
            raise InvalidTransition()
