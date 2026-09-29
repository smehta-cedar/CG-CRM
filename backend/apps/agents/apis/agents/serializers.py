from rest_framework import serializers

from apps.agents.models import LICENSE_STATUSES, Agent, AgentNote, AgentStateLicense
from apps.agents.utils import normalize_aliases


class AddressSerializer(serializers.Serializer):
    street = serializers.CharField(max_length=255, allow_blank=True)
    city = serializers.CharField(max_length=100, allow_blank=True)
    state = serializers.CharField(max_length=2, allow_blank=True, help_text='Two-letter USPS code.')
    zip = serializers.RegexField(
        r'^(\d{5}(-\d{4})?)?$',
        allow_blank=True,
        error_messages={'invalid': 'Enter a five-digit ZIP, or ZIP+4 like 78701-1234.'},
    )


class AgentLicenseSerializer(serializers.ModelSerializer):
    """One licence row as it appears on an agent."""

    state = serializers.CharField(source='state.code', read_only=True)
    status = serializers.ChoiceField(choices=LICENSE_STATUSES, read_only=True)

    class Meta:
        model = AgentStateLicense
        fields = ('id', 'state', 'license_number', 'status', 'start_date', 'end_date', 'life', 'health')
        read_only_fields = fields


class AgentSerializer(serializers.ModelSerializer):
    """How an agent appears in every response."""

    aliases = serializers.ListField(child=serializers.CharField(), read_only=True)
    address = AddressSerializer(read_only=True, allow_null=True)
    licenses = serializers.SerializerMethodField(help_text='Licence rows, in state-code order.')

    class Meta:
        model = Agent
        fields = (
            'id',
            'name',
            'aliases',
            'npn',
            'email',
            'phone',
            'personal_email',
            'personal_phone',
            'address',
            'date_of_birth',
            'join_date',
            'start_date',
            'ssn_last4',
            'licenses',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_licenses(self, agent) -> list:
        rows = sorted(agent.licenses.all(), key=lambda row: row.state.code)
        return AgentLicenseSerializer(rows, many=True).data


class AgentChangeSerializer(serializers.Serializer):
    """One changed field in a note: {"field", "from", "to"}, values as shown."""

    field = serializers.CharField()
    to = serializers.CharField(allow_blank=True)

    def get_fields(self):
        # "from" is a Python keyword, so it can't be declared on the class.
        fields = super().get_fields()
        fields['from'] = serializers.CharField(allow_blank=True)
        return fields


class AgentNoteSerializer(serializers.ModelSerializer):
    """One change-log entry."""

    agent_id = serializers.UUIDField(read_only=True)
    changes = AgentChangeSerializer(many=True, read_only=True)
    created_by = serializers.SerializerMethodField(help_text='The full name of who made the change.')

    class Meta:
        model = AgentNote
        fields = ('id', 'agent_id', 'kind', 'changes', 'created_by', 'created_at')
        read_only_fields = fields

    def get_created_by(self, note) -> str | None:
        user = note.created_by
        return user.full_name if user else None


class LicenseInputSerializer(serializers.Serializer):
    state = serializers.CharField(min_length=2, max_length=2, help_text='Two-letter state code.')
    license_number = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    life = serializers.BooleanField(required=False, default=False, help_text='Covers life insurance.')
    health = serializers.BooleanField(required=False, default=False, help_text='Covers health insurance.')
    start_date = serializers.DateField(
        required=False,
        allow_null=True,
        default=None,
        help_text='YYYY-MM-DD. Left out: today for a new row, unchanged for a kept one.',
    )
    end_date = serializers.DateField(
        required=False,
        allow_null=True,
        default=None,
        help_text='YYYY-MM-DD. Left out: two years on for a new row, unchanged for a kept one.',
    )

    def validate(self, data):
        start, end = data.get('start_date'), data.get('end_date')
        if start and end and end < start:
            raise serializers.ValidationError({'end_date': ['The end date must be on or after the start date.']})
        return data


def _aliases_field():
    # Blank entries are allowed in, then dropped by normalize_aliases.
    return serializers.ListField(
        child=serializers.CharField(max_length=255, allow_blank=True),
        required=False,
        help_text='Other names the agent goes by.',
    )


def _npn_field(required):
    # An NPN is up to 10 digits; the model column leaves room for more.
    return serializers.RegexField(
        r'^\d{1,10}$',
        required=required,
        error_messages={'invalid': 'NPN must be 1 to 10 digits.'},
    )


def _licenses_field():
    return serializers.ListField(
        child=LicenseInputSerializer(),
        required=False,
        help_text='The licensed states with their numbers, dates and lines; replaces the current set.',
    )


class _AgentWriteSerializer(serializers.Serializer):
    aliases = _aliases_field()
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    personal_email = serializers.EmailField(required=False, allow_blank=True)
    personal_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    address = AddressSerializer(required=False, allow_null=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True, help_text='YYYY-MM-DD.')
    join_date = serializers.DateField(required=False, allow_null=True, help_text='YYYY-MM-DD. When they joined the agency.')
    start_date = serializers.DateField(required=False, allow_null=True, help_text='YYYY-MM-DD. Employment start.')
    ssn_last4 = serializers.RegexField(
        r'^\d{4}$',
        required=False,
        allow_blank=True,
        help_text='The last four digits of the SSN only.',
        error_messages={'invalid': 'Enter only the last 4 digits of the SSN.'},
    )
    licenses = _licenses_field()
    is_active = serializers.BooleanField(required=False)

    def validate_aliases(self, value):
        return normalize_aliases(value)


class AgentCreateSerializer(_AgentWriteSerializer):
    name = serializers.CharField(max_length=255)
    npn = _npn_field(required=True)


class AgentUpdateSerializer(_AgentWriteSerializer):
    """Send only the fields that change."""

    name = serializers.CharField(max_length=255, required=False)
    npn = _npn_field(required=False)


class AgentListQuerySerializer(serializers.Serializer):
    search = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Matches name, alias, NPN, email or phone.',
    )
    is_active = serializers.BooleanField(
        required=False,
        allow_null=True,
        help_text='true for active agents, false for inactive ones.',
    )
    state = serializers.CharField(
        required=False,
        allow_blank=True,
        min_length=2,
        max_length=2,
        help_text='Only agents licensed in this state (two-letter code).',
    )
