from rest_framework import serializers

from apps.passwords.apis.passwords.serializers import CarrierSummarySerializer
from apps.policies.models import CarrierPolicy, CarrierPolicyNote, PolicyType


class PolicyTypeSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyType
        fields = ('id', 'name', 'is_active')


class CarrierPolicySerializer(serializers.ModelSerializer):
    """How a carrier policy appears in every response."""

    carrier = CarrierSummarySerializer(read_only=True)
    policy_type = PolicyTypeSummarySerializer(read_only=True, allow_null=True)
    available_states = serializers.ListField(
        child=serializers.CharField(),
        source='state_codes',
        read_only=True,
        help_text='Two-letter state codes, in code order.',
    )

    class Meta:
        model = CarrierPolicy
        fields = (
            'id',
            'carrier',
            'policy_type',
            'name',
            'available_states',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class CarrierPolicyChangeSerializer(serializers.Serializer):
    """One changed field in a note: {"field", "from", "to"}, values as shown."""

    field = serializers.CharField()
    to = serializers.CharField(allow_blank=True)

    def get_fields(self):
        # "from" is a Python keyword, so it can't be declared on the class.
        fields = super().get_fields()
        fields['from'] = serializers.CharField(allow_blank=True)
        return fields


class CarrierPolicyNoteSerializer(serializers.ModelSerializer):
    """One change-log entry."""

    policy_id = serializers.UUIDField(read_only=True)
    changes = CarrierPolicyChangeSerializer(many=True, read_only=True)
    created_by = serializers.SerializerMethodField(help_text='The full name of who made the change.')

    class Meta:
        model = CarrierPolicyNote
        fields = ('id', 'policy_id', 'kind', 'changes', 'created_by', 'created_at')
        read_only_fields = fields

    def get_created_by(self, note) -> str | None:
        user = note.created_by
        return user.full_name if user else None


def _states_field():
    return serializers.ListField(
        child=serializers.CharField(min_length=2, max_length=2),
        required=False,
        help_text="Two-letter state codes the policy can be sold in; each must be on the carrier's available states.",
    )


class CarrierPolicyCreateSerializer(serializers.Serializer):
    carrier = serializers.UUIDField(help_text='The carrier that offers the policy.')
    policy_type = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text='Optional: a row from the policy type catalog. Unknown ones are ignored.',
    )
    name = serializers.CharField(max_length=255)
    available_states = _states_field()
    is_active = serializers.BooleanField(required=False)


class CarrierPolicyUpdateSerializer(serializers.Serializer):
    """Send only the fields that change. The carrier can't change: a policy stays on the carrier it was added to."""

    policy_type = serializers.UUIDField(required=False, allow_null=True, help_text='null clears it.')
    name = serializers.CharField(max_length=255, required=False)
    available_states = _states_field()
    is_active = serializers.BooleanField(required=False)


class CarrierPolicyListQuerySerializer(serializers.Serializer):
    search = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Matches the name.',
    )
    carrier = serializers.UUIDField(required=False, help_text='Only this carrier\'s policies.')
    policy_type = serializers.UUIDField(required=False, help_text='Only policies of this type.')
    is_active = serializers.BooleanField(
        required=False,
        allow_null=True,
        help_text='true for active policies, false for inactive ones.',
    )
