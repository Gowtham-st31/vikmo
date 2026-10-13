from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, MethodNotAllowed
from rest_framework.decorators import action
from django.db.models import Prefetch
from .models import Order, OrderItem
from .serializers import OrderInputSerializer, OrderOutputSerializer
from .services import (
    create_draft_order, 
    update_draft_order,
    confirm_order,
    dispatch_order,
    deliver_order,
    cancel_order
)
from catalogue.views import StandardResultsSetPagination

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.prefetch_related(
        Prefetch('items', queryset=OrderItem.objects.select_related('product'))
    ).order_by('-created_at')
    serializer_class = OrderOutputSerializer
    pagination_class = StandardResultsSetPagination
    lookup_field = 'order_number'
    # Block DELETE on orders
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        dealer_id = self.request.query_params.get('dealer_id')
        status_param = self.request.query_params.get('status')
        if dealer_id:
            qs = qs.filter(dealer_id=dealer_id)
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = OrderInputSerializer(data=request.data)
        if not serializer.is_valid():
            class InputValidationError(ValidationError):
                custom_code = "VALIDATION_ERROR"
            raise InputValidationError(serializer.errors)

        if 'dealer_id' not in serializer.validated_data:
            class InputValidationError(ValidationError):
                custom_code = "VALIDATION_ERROR"
            raise InputValidationError({"dealer_id": ["This field is required."]})
            
        idempotency_key = request.headers.get('Idempotency-Key')
        
        order = create_draft_order(
            dealer_id=serializer.validated_data['dealer_id'],
            items_data=serializer.validated_data['items'],
            idempotency_key=idempotency_key,
            request_body=request.data
        )

        output_serializer = OrderOutputSerializer(order)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        order_number = self.kwargs['order_number']
        
        serializer = OrderInputSerializer(data=request.data)
        if not serializer.is_valid():
            class InputValidationError(ValidationError):
                custom_code = "VALIDATION_ERROR"
            raise InputValidationError(serializer.errors)
        
        order = update_draft_order(
            order_number=order_number,
            items_data=serializer.validated_data['items']
        )
        
        output_serializer = OrderOutputSerializer(order)
        return Response(output_serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed('DELETE')

    @action(detail=True, methods=['post'])
    def confirm(self, request, order_number=None):
        order = confirm_order(order_number)
        return Response(OrderOutputSerializer(order).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='dispatch')
    def dispatch_order_action(self, request, order_number=None):
        order = dispatch_order(order_number)
        return Response(OrderOutputSerializer(order).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def deliver(self, request, order_number=None):
        order = deliver_order(order_number)
        return Response(OrderOutputSerializer(order).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def cancel(self, request, order_number=None):
        order = cancel_order(order_number)
        return Response(OrderOutputSerializer(order).data, status=status.HTTP_200_OK)
