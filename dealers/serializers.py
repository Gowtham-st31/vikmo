from rest_framework import serializers
from .models import Dealer

class DealerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dealer
        fields = ['id', 'dealer_code', 'name', 'city', 'phone', 'email', 'gstin', 'credit_limit']
        # Disable DRF's auto-generated UniqueValidator on dealer_code so we can
        # raise 409 DUPLICATE ourselves in the view instead of 400.
        extra_kwargs = {
            'dealer_code': {'validators': []},
        }
