from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import Dealer
from .serializers import DealerSerializer
from catalogue.views import StandardResultsSetPagination

class DealerViewSet(viewsets.ModelViewSet):
    queryset = Dealer.objects.all().order_by('id')
    serializer_class = DealerSerializer
    pagination_class = StandardResultsSetPagination

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
                    default_detail = "Dealer code already exists."
                raise DuplicateException()
            raise
            
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
