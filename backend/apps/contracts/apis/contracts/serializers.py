from rest_framework import serializers

from apps.agents.models import Agent
from apps.carriers.models import Carrier
from apps.contracts.models import CarrierContract, CarrierContractNote
# One schema component each for the {id, name, is_active} summaries.
from apps.passwords.apis.passwords.serializers import AgentSummarySerializer, CarrierSummarySerializer


class ContractSerializer(serializers.ModelSerializer):
    """How a contract appears in every response."""

    agent = AgentSummarySerializer(read_only=True)
    carrier = CarrierSummarySerializer(read_only=True)
    appointed_states = serializers.ListField(
        child=serializers.CharField(),
        source='state_codes',
        read_only=True,
        help_text='Two-letter state codes, in code order.',
    )

    class Meta:
        model = CarrierContract
        fields = (
            'id',
            'agent',
            'carrier',
            'writing_number',
            'appointed_states',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class ContractChangeSerializer(serializers.Serializer):
    """One changed field in a note: {"field", "from", "to"}, values as shown."""

    field = serializers.CharField()
    to = serializers.CharField(allow_blank=True)

    def get_fields(self):
        # "from" is a Python keyword, so it can't be declared on the class.
        fields = super().get_fields()
        fields['from'] = serializers.CharField(allow_blank=True)
        return fields


class ContractNoteSerializer(serializers.ModelSerializer):
    """One change-log entry."""

    contract_id = serializers.UUIDField(read_only=True)
    changes = ContractChangeSerializer(many=True, read_only=True)
    created_by = serializers.SerializerMethodField(help_text='The full name of who made the change.')

    class Meta:
        model = CarrierContractNote
        fields = ('id', 'contract_id', 'kind', 'changes', 'created_by', 'created_at')
        read_only_fields = fields

    def get_created_by(self, note) -> str | None:
        user = note.created_by
        return user.full_name if user else None


# Inactive agents and carriers can still hold contracts; only deleted ones are out.
def _agent_id_field(required):
    return serializers.PrimaryKeyRelatedField(
        source='agent',
        queryset=Agent.objects.all(),
        pk_field=serializers.UUIDField(),
        required=required,
    )


def _carrier_id_field(required):
    return serializers.PrimaryKeyRelatedField(
        source='carrier',
        queryset=Carrier.objects.all(),
        pk_field=serializers.UUIDField(),
        required=required,
    )


def _states_field():
    return serializers.ListField(
        child=serializers.CharField(min_length=2, max_length=2),
        required=False,
        help_text='Two-letter state codes the agent is appointed in with this carrier.',
    )


class ContractCreateSerializer(serializers.Serializer):
    agent_id = _agent_id_field(required=True)
    carrier_id = _carrier_id_field(required=True)
    writing_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    appointed_states = _states_field()


class ContractUpdateSerializer(serializers.Serializer):
    """Send only the fields that change."""

    agent_id = _agent_id_field(required=False)
    carrier_id = _carrier_id_field(required=False)
    writing_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    appointed_states = _states_field()


class ContractListQuerySerializer(serializers.Serializer):
    search = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Matches agent name, carrier name or writing number.',
    )
    agent_id = serializers.UUIDField(required=False)
    carrier_id = serializers.UUIDField(required=False)
    state = serializers.CharField(
        required=False,
        allow_blank=True,
        min_length=2,
        max_length=2,
        help_text='Only contracts appointed in this state (two-letter code).',
    )
