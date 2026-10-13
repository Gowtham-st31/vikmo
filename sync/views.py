from rest_framework.views import APIView
from rest_framework.response import Response
from .services import run_supplier_sync

class SupplierSyncView(APIView):
    def post(self, request, *args, **kwargs):
        result = run_supplier_sync()
        return Response(result)
