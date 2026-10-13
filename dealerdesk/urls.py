from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from catalogue.views import ProductViewSet, InventoryView
from dealers.views import DealerViewSet
from orders.views import OrderViewSet
from django.http import JsonResponse

from sync.views import SupplierSyncView

def health_check(request):
    return JsonResponse({"status": "ok"})

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'dealers', DealerViewSet, basename='dealer')
router.register(r'orders', OrderViewSet, basename='order')

urlpatterns = [
    path('api/health/', health_check),
    path('api/inventory/<str:sku>/', InventoryView.as_view(), name='inventory-update'),
    path('api/sync/supplier/', SupplierSyncView.as_view(), name='sync-supplier'),
    path('api/assistant/', include('assistant.urls')),
    path('api/', include('ml.urls')),
    path('api/', include(router.urls)),
]
