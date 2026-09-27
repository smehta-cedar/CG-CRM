from rest_framework import serializers

from apps.agents.models import Agent
from apps.carriers.models import Carrier
from apps.passwords.apis.passwords.serializers import AgentSummarySerializer, CarrierSummarySerializer
from apps.requests.models import REQUEST_STATUSES, REQUEST_TYPES, Request
from apps.storefront.apis.products.serializers import ProductSummarySerializer
from apps.storefront.models import Product

# The types the Create-a-request dialog files: every one names an agent.
AGENT_REQUEST_TYPES = tuple((code, label) for code, label in REQUEST_TYPES if code != 'merch')


class RequestSerializer(serializers.ModelSerializer):
    """How a request appears in every response. Columns a type doesn't use
    come back null or blank."""

    agent = AgentSummarySerializer(read_only=True, allow_null=True)
    carrier = CarrierSummarySerializer(read_only=True, allow_null=True)
    state = serializers.SerializerMethodField(help_text='Two-letter state code, or null.')
    product = ProductSummarySerializer(read_only=True, allow_null=True)
    created_by = serializers.SerializerMethodField(help_text='The full name of who filed it.')

    class Meta:
        model = Request
        fields = (
            'id',
            'type',
            'status',
            'note',
            'agent',
            'carrier',
            'state',
            'start_date',
            'end_date',
            'product',
            'buyer_name',
            'email',
            'phone',
            'address',
            'size',
            'color',
            'quantity',
            'created_by',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_state(self, request) -> str | None:
        return request.state.code if request.state else None

    def get_created_by(self, request) -> str | None:
        user = request.created_by
        return user.full_name if user else None


class RequestCreateSerializer(serializers.Serializer):
    """An agent's request. Which of the optional fields are needed depends on
    the type (checked in the view)."""

    type = serializers.ChoiceField(choices=AGENT_REQUEST_TYPES)
    agent_id = serializers.PrimaryKeyRelatedField(
        source='agent', queryset=Agent.objects.all(), pk_field=serializers.UUIDField()
    )
    carrier_id = serializers.PrimaryKeyRelatedField(
        source='carrier', queryset=Carrier.objects.all(), pk_field=serializers.UUIDField(), required=False, allow_null=True
    )
    state = serializers.CharField(min_length=2, max_length=2, required=False, allow_blank=True)
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True)


class MerchRequestCreateSerializer(serializers.Serializer):
    """An order from the public shop, filed by the shop's service account.
    `color` is the product colour's id; the order stores its label."""

    product_id = serializers.PrimaryKeyRelatedField(
        source='product', queryset=Product.objects.filter(is_active=True), pk_field=serializers.UUIDField()
    )
    buyer_name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20)
    address = serializers.CharField()
    size = serializers.CharField(max_length=20)
    color = serializers.CharField(max_length=50)
    quantity = serializers.IntegerField(min_value=1, max_value=999)
    note = serializers.CharField(required=False, allow_blank=True)


class RequestUpdateSerializer(serializers.Serializer):
    """HR's decision, and the note. Send only the fields that change."""

    status = serializers.ChoiceField(choices=REQUEST_STATUSES, required=False)
    note = serializers.CharField(required=False, allow_blank=True)


class RequestListQuerySerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=REQUEST_TYPES, required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=REQUEST_STATUSES, required=False, allow_blank=True)
    agent_id = serializers.UUIDField(required=False)
