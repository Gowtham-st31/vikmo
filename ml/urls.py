from django.urls import path
from .views import ForecastView, ReorderSuggestionsView

urlpatterns = [
    path('forecast/<str:sku>/', ForecastView.as_view(), name='forecast_detail'),
    path('reorder-suggestions/', ReorderSuggestionsView.as_view(), name='reorder_suggestions'),
]
