from rest_framework import serializers

from apps.carriers.models import LINES_OF_BUSINESS
from apps.passwords.apis.passwords.serializers import AgentSummarySerializer, CarrierSummarySerializer
from apps.policies.models import Certification, CertificationNote


class CertificationSerializer(serializers.ModelSerializer):
    """How a certification appears in every response."""

    agent = AgentSummarySerializer(read_only=True)
    carrier = CarrierSummarySerializer(read_only=True, allow_null=True)
    file_name = serializers.SerializerMethodField(
        help_text='The uploaded PDF name, or null when there is none. Download it from /certifications/{id}/file/.'
    )

    class Meta:
        model = Certification
        fields = (
            'id',
            'agent',
            'carrier',
            'line_of_business',
            'due_date',
            'start_date',
            'end_date',
            'is_verified',
            'file_name',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_file_name(self, certification) -> str | None:
        return certification.file_name if certification.file else None


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


def _carrier_field():
    return serializers.UUIDField(required=False, allow_null=True)


def _line_field():
    return serializers.ChoiceField(
        choices=LINES_OF_BUSINESS,
        required=False,
        allow_blank=True,
        help_text="The certification's sub type: one of the carrier's lines of business.",
    )


def _file_field():
    return serializers.FileField(
        required=False,
        help_text='A PDF of at most 10 MB, sent as multipart form data. Replaces the stored file; leave it out to keep it.',
    )


class CertificationCreateSerializer(serializers.Serializer):
    agent = serializers.UUIDField()
    carrier = _carrier_field()
    line_of_business = _line_field()
    due_date = serializers.DateField(
        required=False, allow_null=True, help_text='Defaults to the next yearly deadline.'
    )
    start_date = _date_field()
    end_date = _date_field()
    is_verified = serializers.BooleanField(required=False)
    file = _file_field()
    is_active = serializers.BooleanField(required=False)


class CertificationUpdateSerializer(serializers.Serializer):
    """Send only the fields that change."""

    agent = serializers.UUIDField(required=False)
    carrier = _carrier_field()
    line_of_business = _line_field()
    due_date = _date_field()
    start_date = _date_field()
    end_date = _date_field()
    is_verified = serializers.BooleanField(required=False)
    file = _file_field()
    is_active = serializers.BooleanField(required=False)


class CertificationListQuerySerializer(serializers.Serializer):
    agent = serializers.UUIDField(required=False, help_text="Only this agent's certifications.")
    carrier = serializers.UUIDField(required=False, help_text="Only this carrier's certifications.")
    line_of_business = serializers.ChoiceField(
        choices=LINES_OF_BUSINESS, required=False, help_text='Only certifications for this line of business.'
    )
