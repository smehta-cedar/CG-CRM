from rest_framework import serializers

from apps.passwords.apis.passwords.serializers import AgentSummarySerializer
from apps.policies.apis.carrier_policies.serializers import PolicyTypeSummarySerializer
from apps.policies.models import Certification, CertificationNote


class CertificationSerializer(serializers.ModelSerializer):
    """How a certification appears in every response."""

    agent = AgentSummarySerializer(read_only=True)
    policy_type = PolicyTypeSummarySerializer(read_only=True)

    class Meta:
        model = Certification
        fields = (
            'id',
            'agent',
            'policy_type',
            'start_date',
            'end_date',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class CertificationChangeSerializer(serializers.Serializer):
    """One changed field in a note: {"field", "from", "to"}, values as shown."""

    field = serializers.CharField()
    to = serializers.CharField(allow_blank=True)

    def get_fields(self):
        # "from" is a Python keyword, so it can't be declared on the class.
        fields = super().get_fields()
        fields['from'] = serializers.CharField(allow_blank=True)
        return fields


class CertificationNoteSerializer(serializers.ModelSerializer):
    """One change-log entry."""

    certification_id = serializers.UUIDField(read_only=True)
    changes = CertificationChangeSerializer(many=True, read_only=True)
    created_by = serializers.SerializerMethodField(help_text='The full name of who made the change.')

    class Meta:
        model = CertificationNote
        fields = ('id', 'certification_id', 'kind', 'changes', 'created_by', 'created_at')
        read_only_fields = fields

    def get_created_by(self, note) -> str | None:
        user = note.created_by
        return user.full_name if user else None


def _date_field():
    return serializers.DateField(required=False, allow_null=True)


class CertificationCreateSerializer(serializers.Serializer):
    agent = serializers.UUIDField()
    policy_type = serializers.UUIDField(help_text='A row from the policy type catalog.')
    start_date = _date_field()
    end_date = _date_field()
    is_active = serializers.BooleanField(required=False)


class CertificationUpdateSerializer(serializers.Serializer):
    """Send only the fields that change. A duplicate pair is reported under
    whichever of agent / policy_type was sent (policy_type when both were)."""

    agent = serializers.UUIDField(required=False)
    policy_type = serializers.UUIDField(required=False)
    start_date = _date_field()
    end_date = _date_field()
    is_active = serializers.BooleanField(required=False)


class CertificationListQuerySerializer(serializers.Serializer):
    agent = serializers.UUIDField(required=False, help_text="Only this agent's certifications.")
    policy_type = serializers.UUIDField(required=False, help_text='Only certifications for this policy type.')
