from rest_framework import serializers

from apps.agency.models import Agency
from apps.agents.models import Agent
from apps.carriers.models import Carrier
from apps.passwords.models import PASSWORD_STATUSES, Password, PasswordNote


class AgentSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Agent
        fields = ('id', 'name', 'is_active')


class AgencySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Agency
        fields = ('id', 'name', 'is_active')


class CarrierSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Carrier
        fields = ('id', 'name', 'status', 'is_active')


class PasswordSerializer(serializers.ModelSerializer):
    """How a password appears in every response. `agent` or `agency` is set,
    the other null. The portal password is included: the page shows and
    copies it."""

    agent = AgentSummarySerializer(read_only=True)
    agency = AgencySummarySerializer(read_only=True)
    carrier = CarrierSummarySerializer(read_only=True)
    status = serializers.ChoiceField(choices=PASSWORD_STATUSES, read_only=True)

    class Meta:
        model = Password
        fields = (
            'id',
            'agent',
            'agency',
            'carrier',
            'username',
            'portal_password',
            'link',
            'status',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class PasswordChangeSerializer(serializers.Serializer):
    """One changed field in a note: {"field", "from", "to", "redacted"?}."""

    field = serializers.CharField()
    to = serializers.CharField(allow_blank=True)
    redacted = serializers.BooleanField(required=False)

    def get_fields(self):
        # "from" is a Python keyword, so it can't be declared on the class.
        fields = super().get_fields()
        fields['from'] = serializers.CharField(allow_blank=True)
        return fields


class PasswordNoteSerializer(serializers.ModelSerializer):
    """One change-log entry."""

    password_id = serializers.UUIDField(read_only=True)
    changes = PasswordChangeSerializer(many=True, read_only=True)
    created_by = serializers.SerializerMethodField(help_text='The full name of who made the change.')

    class Meta:
        model = PasswordNote
        fields = ('id', 'password_id', 'kind', 'changes', 'created_by', 'created_at')
        read_only_fields = fields

    def get_created_by(self, note) -> str | None:
        user = note.created_by
        return user.full_name if user else None


# The querysets are lazy and re-run on every request. Inactive agents and
# carriers can still hold passwords; only deleted ones are out. A password
# takes agent_id or agency_id: the other is null or left out.
def _agent_id_field():
    return serializers.PrimaryKeyRelatedField(
        source='agent',
        queryset=Agent.objects.all(),
        pk_field=serializers.UUIDField(),
        required=False,
        allow_null=True,
    )


def _agency_id_field():
    return serializers.PrimaryKeyRelatedField(
        source='agency',
        queryset=Agency.objects.all(),
        pk_field=serializers.UUIDField(),
        required=False,
        allow_null=True,
    )


def _carrier_id_field(required):
    return serializers.PrimaryKeyRelatedField(
        source='carrier',
        queryset=Carrier.objects.all(),
        pk_field=serializers.UUIDField(),
        required=required,
    )


def _portal_password_field(required):
    # Not trimmed: spaces and case can matter in a password.
    return serializers.CharField(max_length=255, required=required, allow_blank=True, trim_whitespace=False)


def _link_field():
    return serializers.URLField(
        max_length=2000,
        required=False,
        allow_blank=True,
        help_text="The carrier portal's sign-in page. Blank for none.",
    )


class PasswordCreateSerializer(serializers.Serializer):
    """Send agent_id or agency_id, not both."""

    agent_id = _agent_id_field()
    agency_id = _agency_id_field()
    carrier_id = _carrier_id_field(required=True)
    username = serializers.CharField(max_length=255)
    portal_password = _portal_password_field(required=True)
    link = _link_field()
    status = serializers.ChoiceField(choices=PASSWORD_STATUSES, required=False)


class PasswordUpdateSerializer(serializers.Serializer):
    """Send only the fields that change. Setting agent_id clears the agency,
    and the other way round."""

    agent_id = _agent_id_field()
    agency_id = _agency_id_field()
    carrier_id = _carrier_id_field(required=False)
    username = serializers.CharField(max_length=255, required=False)
    portal_password = _portal_password_field(required=False)
    link = _link_field()
    status = serializers.ChoiceField(choices=PASSWORD_STATUSES, required=False)


class PasswordListQuerySerializer(serializers.Serializer):
    search = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Matches portal username, agent or agency name, or carrier name.',
    )
    agent_id = serializers.UUIDField(required=False)
    agency_id = serializers.UUIDField(required=False)
    carrier_id = serializers.UUIDField(required=False)
    status = serializers.ChoiceField(choices=PASSWORD_STATUSES, required=False, allow_blank=True)
