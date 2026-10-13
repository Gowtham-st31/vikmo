import time
import requests
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.db import transaction
from catalogue.models import Product, Inventory
from rest_framework.exceptions import APIException

class SupplierUnavailable(APIException):
    status_code = 502
    default_code = 'SUPPLIER_UNAVAILABLE'
    default_detail = 'Supplier sync could not fetch the full feed.'

# Accept "500" (integer), "500.5" (1 decimal), "500.50" (2 decimals)
PRICE_REGEX = re.compile(r"^\d+(\.\d{1,2})?$")

def is_valid_price(price_str):
    if not isinstance(price_str, str):
        price_str = str(price_str)
    if not PRICE_REGEX.match(price_str):
        return False
    try:
        val = Decimal(price_str)
        return val > 0
    except InvalidOperation:
        return False

def parse_retry_after(raw_value, default=1) -> int:
    """Parse Retry-After header safely. Non-integers (or non-positive values) default to 1 second."""
    if raw_value is None:
        return default
    try:
        val = int(raw_value)
        return val if val > 0 else default
    except (ValueError, TypeError):
        return default

# Maximum wall-clock time for the entire sync (contract: 120 seconds)
SYNC_DEADLINE_SECONDS = 120

def fetch_supplier_feed():
    url = f"{settings.SUPPLIER_API_URL.rstrip('/')}/v1/products"
    headers = {"X-Api-Key": settings.SUPPLIER_API_KEY}
    cursor = None
    
    feed_items = []
    pages_fetched = 0
    requests_made = 0
    sync_start = time.monotonic()
    
    while True:
        params = {"limit": 20}
        if cursor:
            params["cursor"] = cursor
            
        attempts = 0
        success = False
        while attempts < 5:
            elapsed = time.monotonic() - sync_start
            if elapsed >= SYNC_DEADLINE_SECONDS:
                raise SupplierUnavailable("Sync exceeded 120-second deadline.")
            attempts += 1
            requests_made += 1
            try:
                response = requests.get(url, headers=headers, params=params, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    feed_items.extend(data.get("items", []))
                    cursor = data.get("next_cursor")
                    pages_fetched += 1
                    success = True
                    break
                elif response.status_code == 429:
                    retry_after = parse_retry_after(response.headers.get("Retry-After"))
                    # Cap wait so the whole sync stays under 120 seconds
                    remaining = SYNC_DEADLINE_SECONDS - (time.monotonic() - sync_start)
                    if retry_after > remaining:
                        raise SupplierUnavailable("Retry-After exceeds remaining sync budget.")
                    time.sleep(retry_after)
                elif response.status_code in (401, 500, 502, 503):
                    time.sleep(1)
                else:
                    time.sleep(1)
            except requests.RequestException:
                time.sleep(1)
        
        if not success:
            raise SupplierUnavailable()
            
        if not cursor:
            break
            
    return feed_items, pages_fetched, requests_made

def run_supplier_sync():
    feed_items, pages_fetched, requests_made = fetch_supplier_feed()
    
    rejected = []
    valid_items = {}
    
    for item in feed_items:
        supplier_sku = item.get("supplier_sku", "")
        sku = item.get("sku", "")
        price = str(item.get("price", ""))
        
        if not sku or str(sku).strip() == "":
            rejected.append({"supplier_sku": supplier_sku, "reason": "missing or empty sku"})
            continue
            
        if not is_valid_price(price):
            rejected.append({"supplier_sku": supplier_sku, "reason": "invalid price"})
            continue
            
        # Treat missing or invalid updated_at as a rejected item (not a crash)
        raw_updated_at = item.get("updated_at")
        if not raw_updated_at or not isinstance(raw_updated_at, str):
            rejected.append({"supplier_sku": supplier_sku, "reason": "missing updated_at"})
            continue
        try:
            updated_at = datetime.fromisoformat(raw_updated_at.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            rejected.append({"supplier_sku": supplier_sku, "reason": "invalid updated_at"})
            continue
        
        # Resolve duplicates using latest updated_at
        if sku in valid_items:
            existing = valid_items[sku]
            existing_time = datetime.fromisoformat(existing["updated_at"].replace('Z', '+00:00'))
            if updated_at > existing_time:
                valid_items[sku] = item
        else:
            valid_items[sku] = item
            
    created = 0
    updated = 0
    unchanged = 0
    
    with transaction.atomic():
        # Load all existing products that match the SKUs in the valid feed
        existing_products = Product.objects.in_bulk(list(valid_items.keys()), field_name='sku')
        
        new_products = []
        update_products = []
        new_inventories = []
        
        for sku, item in valid_items.items():
            name = item.get("name", "").strip()
            category = item.get("category", "").strip()
            brand = item.get("brand", "").strip()
            vehicle_fitment = item.get("vehicle_fitment", "").strip()
            description = item.get("description", "").strip()
            price_val = Decimal(str(item.get("price")))
            
            if sku in existing_products:
                prod = existing_products[sku]
                changed = False
                
                if prod.name != name:
                    prod.name = name
                    changed = True
                if prod.category != category:
                    prod.category = category
                    changed = True
                if prod.brand != brand:
                    prod.brand = brand
                    changed = True
                if prod.vehicle_fitment != vehicle_fitment:
                    prod.vehicle_fitment = vehicle_fitment
                    changed = True
                if prod.description != description:
                    prod.description = description
                    changed = True
                if prod.price != price_val:
                    prod.price = price_val
                    changed = True
                    
                if changed:
                    update_products.append(prod)
                    updated += 1
                else:
                    unchanged += 1
            else:
                new_products.append(Product(
                    sku=sku,
                    name=name,
                    category=category,
                    brand=brand,
                    vehicle_fitment=vehicle_fitment,
                    description=description,
                    price=price_val
                ))
                created += 1

        if new_products:
            Product.objects.bulk_create(new_products)
            for p in new_products:
                new_inventories.append(Inventory(product_id=p.sku, quantity=0))
            Inventory.objects.bulk_create(new_inventories)
            
        if update_products:
            Product.objects.bulk_update(update_products, ['name', 'category', 'brand', 'vehicle_fitment', 'description', 'price'])
            
    return {
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "rejected": rejected,
        "pages_fetched": pages_fetched,
        "requests_made": requests_made
    }
