from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from django.shortcuts import get_object_or_404
from .models import Product, Inventory
from .serializers import ProductSerializer, InventoryUpdateSerializer

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related('inventory').all().order_by('sku')
    serializer_class = ProductSerializer
    pagination_class = StandardResultsSetPagination
    lookup_field = 'sku'

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search', None)
        category = self.request.query_params.get('category', None)
        vehicle = self.request.query_params.get('vehicle', None)

        if search:
            queryset = queryset.filter(
                Q(sku__icontains=search) |
                Q(name__icontains=search) |
                Q(brand__icontains=search)
            )
        if category:
            queryset = queryset.filter(category=category)
        if vehicle:
            queryset = queryset.filter(vehicle_fitment__icontains=vehicle)
            
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            self.perform_create(serializer)
        except Exception as e:
            from django.db import IntegrityError
            if isinstance(e, IntegrityError) or "duplicate key" in str(e).lower():
                from rest_framework.exceptions import APIException
                class DuplicateException(APIException):
                    status_code = 409
                    custom_code = "DUPLICATE"
                    default_detail = "Product SKU already exists."
                raise DuplicateException()
            raise
        
        # Create inventory with 0 stock
        Inventory.objects.create(product=serializer.instance, quantity=0)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class InventoryView(APIView):
    def put(self, request, sku):
        product = get_object_or_404(Product, sku=sku)
        serializer = InventoryUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        qty = serializer.validated_data['quantity']
        inventory, created = Inventory.objects.get_or_create(product=product)
        inventory.quantity = qty
        inventory.save()
        
        return Response({"sku": sku, "quantity": qty})
