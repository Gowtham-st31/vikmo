from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import csv
import math
import os
from django.conf import settings
import pandas as pd
from catalogue.models import Product, Inventory

class ForecastView(APIView):
    def get(self, request, sku, *args, **kwargs):
        forecast_path = os.path.join(settings.BASE_DIR, 'ml', 'forecast.csv')
        if not os.path.exists(forecast_path):
            return Response({"error": {"code": "NOT_FOUND", "message": "forecast.csv not found", "details": []}}, status=status.HTTP_404_NOT_FOUND)
            
        forecast_data = []
        with open(forecast_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['sku'] == sku:
                    forecast_data.append({
                        "week_start": row['week_start'],
                        "forecast_units": float(row['forecast_units'])
                    })
        
        if not forecast_data:
            return Response({"error": {"code": "NOT_FOUND", "message": "SKU not found in forecast", "details": []}}, status=status.HTTP_404_NOT_FOUND)
            
        return Response({
            "sku": sku,
            "forecast": forecast_data
        })

class ReorderSuggestionsView(APIView):
    def get(self, request, *args, **kwargs):
        data_dir = settings.DATA_DIR
        ml_dir = os.path.join(settings.BASE_DIR, 'ml')
        
        # 1. Read forecast.csv
        forecast_path = os.path.join(ml_dir, 'forecast.csv')
        if not os.path.exists(forecast_path):
            return Response({"error": {"code": "NOT_FOUND", "message": "forecast.csv missing", "details": []}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        forecast_df = pd.read_csv(forecast_path)
        
        # 2. Read lead_times.csv
        lead_times_path = os.path.join(data_dir, 'lead_times.csv')
        lead_times_df = pd.read_csv(lead_times_path)
        
        # 3. Read sales_history.csv to compute sigma
        sales_path = os.path.join(data_dir, 'sales_history.csv')
        sales_df = pd.read_csv(sales_path)
        sales_df['week_start'] = pd.to_datetime(sales_df['week_start'])
        
        results = []
        
        # Load live stock from DB
        # To avoid N queries, we can get all inventory at once
        skus = lead_times_df['sku'].tolist()
        inventories = Inventory.objects.filter(product__sku__in=skus).select_related('product')
        stock_map = {inv.product.sku: inv.quantity for inv in inventories}
        
        for _, lt_row in lead_times_df.iterrows():
            sku = lt_row['sku']
            L = int(lt_row['lead_time_weeks'])
            
            # Forecast for first L weeks
            sku_forecast = forecast_df[forecast_df['sku'] == sku].sort_values('week_start').head(L)
            lead_time_demand = float(sku_forecast['forecast_units'].sum())
            
            # Sigma: Sample std (n-1) over most recent 12 weeks of sales
            sku_sales = sales_df[sales_df['sku'] == sku].sort_values('week_start', ascending=False).head(12)
            if len(sku_sales) > 1:
                sigma = float(sku_sales['units_sold'].std(ddof=1))
            elif len(sku_sales) == 1:
                sigma = 0.0
            else:
                sigma = 0.0
                
            safety_stock = math.ceil(1.65 * sigma * math.sqrt(L))
            reorder_point = lead_time_demand + safety_stock
            
            current_stock = stock_map.get(sku, 0)
            reorder_qty = max(0, math.ceil(reorder_point - current_stock))
            
            results.append({
                "sku": sku,
                "current_stock": current_stock,
                "lead_time_weeks": L,
                "lead_time_demand": round(lead_time_demand, 4), # for exactness
                "safety_stock": safety_stock,
                "reorder_point": round(reorder_point, 4),
                "reorder_qty": int(reorder_qty)
            })
            
        return Response({"results": results})
