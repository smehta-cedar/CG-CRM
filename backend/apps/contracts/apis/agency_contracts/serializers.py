from rest_framework import serializers

from apps.agency.models import Agency
from apps.contracts.models import AgencyCarrierContract, AgencyCarrierContractNote
# One schema component for the carrier's {id, name, is_active} summary.
from apps.passwords.apis.passwords.serializers import CarrierSummarySerializer
from apps.policies.models import CarrierPolicy


class AgencySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Agency
        fields = ('id', 'name', 'is_active')


class CarrierPolicySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = CarrierPolicy
        fields = ('id', 'name', 'is_active')


class AgencyContractSerializer(serializers.ModelSerializer):
    """How an agency contract appears in every response. The password is
    included: the profile's edit dialog shows it."""

    agency = AgencySummarySerializer(read_only=True)
    carrier = CarrierSummarySerializer(read_only=True)
    policies = serializers.SerializerMethodField(help_text='Covered carrier policies, in name order.')

    class Meta:
        model = AgencyCarrierContract
        fields = (
            'id',
            'agency',
            'carrier',
            'contract_number',
            'policies',
            'username',
            'password',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_policies(self, contract) -> list[dict]:
        policies = sorted(contract.policies.all(), key=lambda policy: policy.name.lower())
        return CarrierPolicySummarySerializer(policies, many=True).data


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


def _policies_field():
    return serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        help_text="The carrier's policies this contract covers. Empty means none.",
    )


def _login_field():
    # Not trimmed: spaces can matter in a password. The view strips the username.
    return serializers.CharField(max_length=255, required=False, allow_blank=True, trim_whitespace=False)


class AgencyContractCreateSerializer(serializers.Serializer):
    agency = serializers.UUIDField()
    carrier = serializers.UUIDField(help_text='One live agency contract per carrier.')
    contract_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    policies = _policies_field()
    username = _login_field()
    password = _login_field()
    is_active = serializers.BooleanField(required=False)


class AgencyContractUpdateSerializer(serializers.Serializer):
    """Send only the fields that change."""

    agency = serializers.UUIDField(required=False)
    carrier = serializers.UUIDField(required=False)
    contract_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    policies = _policies_field()
    username = _login_field()
    password = _login_field()
    is_active = serializers.BooleanField(required=False)


class AgencyContractListQuerySerializer(serializers.Serializer):
    agency = serializers.UUIDField(required=False, help_text="Only this agency's contracts.")
    carrier = serializers.UUIDField(required=False, help_text="Only this carrier's contract.")
