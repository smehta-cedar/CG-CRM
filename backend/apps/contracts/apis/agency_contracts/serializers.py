from rest_framework import serializers

from apps.agency.models import Agency
from apps.contracts.models import AgencyCarrierContract, AgencyCarrierContractNote
# One schema component for the carrier's {id, name, is_active} summary.
from apps.passwords.apis.passwords.serializers import CarrierSummarySerializer
from apps.policies.models import PolicyType


class AgencySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Agency
        fields = ('id', 'name', 'is_active')


class PolicyTypeSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyType
        fields = ('id', 'name', 'is_active')


class AgencyContractSerializer(serializers.ModelSerializer):
    """How an agency contract appears in every response."""

    agency = AgencySummarySerializer(read_only=True)
    carrier = CarrierSummarySerializer(read_only=True)
    policy_types = serializers.SerializerMethodField(help_text='Covered policy types, in name order.')

    class Meta:
        model = AgencyCarrierContract
        fields = (
            'id',
            'agency',
            'carrier',
            'contract_number',
            'policy_types',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_policy_types(self, contract) -> list[dict]:
        policy_types = sorted(contract.policy_types.all(), key=lambda policy_type: policy_type.name.lower())
        return PolicyTypeSummarySerializer(policy_types, many=True).data


class AgencyContractChangeSerializer(serializers.Serializer):
    """One changed field in a note: {"field", "from", "to"}, values as shown."""

    field = serializers.CharField()
    to = serializers.CharField(allow_blank=True)

    def get_fields(self):
        # "from" is a Python keyword, so it can't be declared on the class.
        fields = super().get_fields()
        fields['from'] = serializers.CharField(allow_blank=True)
        return fields


class AgencyContractNoteSerializer(serializers.ModelSerializer):
    """One change-log entry."""

    contract_id = serializers.UUIDField(read_only=True)
    changes = AgencyContractChangeSerializer(many=True, read_only=True)
    created_by = serializers.SerializerMethodField(help_text='The full name of who made the change.')

    class Meta:
        model = AgencyCarrierContractNote
        fields = ('id', 'contract_id', 'kind', 'changes', 'created_by', 'created_at')
        read_only_fields = fields

    def get_created_by(self, note) -> str | None:
        user = note.created_by
        return user.full_name if user else None


def _policy_types_field():
    return serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        help_text='The policy types this contract covers. Empty means none.',
    )


class AgencyContractCreateSerializer(serializers.Serializer):
    agency = serializers.UUIDField()
    carrier = serializers.UUIDField(help_text='One live agency contract per carrier.')
    contract_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    policy_types = _policy_types_field()
    is_active = serializers.BooleanField(required=False)


class AgencyContractUpdateSerializer(serializers.Serializer):
    """Send only the fields that change."""

    agency = serializers.UUIDField(required=False)
    carrier = serializers.UUIDField(required=False)
    contract_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    policy_types = _policy_types_field()
    is_active = serializers.BooleanField(required=False)


class AgencyContractListQuerySerializer(serializers.Serializer):
    agency = serializers.UUIDField(required=False, help_text="Only this agency's contracts.")
    carrier = serializers.UUIDField(required=False, help_text="Only this carrier's contract.")
