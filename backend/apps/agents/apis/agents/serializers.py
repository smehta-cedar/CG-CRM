from rest_framework import serializers

from apps.agents.models import AGENT_STATUSES, LICENSE_STATUSES, Agent, AgentNote, AgentStateLicense
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
    status = serializers.ChoiceField(choices=LICENSE_STATUSES, source='current_status', read_only=True)

    class Meta:
        model = AgentStateLicense
        fields = ('id', 'state', 'license_number', 'status', 'start_date', 'end_date', 'renewing', 'life', 'health')
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
            'first_name',
            'last_name',
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
            'remarks',
            'licenses',
            'status',
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
    status = serializers.ChoiceField(
        choices=LICENSE_STATUSES,
        required=False,
        allow_null=True,
        default=None,
        help_text='Left out: active for a new row, unchanged for a kept one.',
    )
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
        help_text='YYYY-MM-DD. Left out: none for a new row, unchanged for a kept one.',
    )
    renewing = serializers.BooleanField(
        required=False,
        allow_null=True,
        default=None,
        help_text=(
            'A renewal is under way. Left out: off for a new row, unchanged for a kept one. '
            'Cleared on save unless the end date is within 60 days or passed.'
        ),
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


def _name_part_field(help_text):
    return serializers.CharField(max_length=100, required=False, allow_blank=True, help_text=help_text)


class _AgentWriteSerializer(serializers.Serializer):
    first_name = _name_part_field('With last_name, builds `name`. Includes any middle name.')
    last_name = _name_part_field('With first_name, builds `name`.')
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
    remarks = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True, help_text='Free-text notes.')
    licenses = _licenses_field()
    status = serializers.ChoiceField(choices=AGENT_STATUSES, required=False)
    is_active = serializers.BooleanField(
        required=False,
        help_text='Ignored when status is sent. false sets status to inactive; true sets it to active if it was inactive.',
    )

    def validate_aliases(self, value):
        return normalize_aliases(value)


class AgentCreateSerializer(_AgentWriteSerializer):
    """Send first_name (and last_name), or a full `name` to split."""

    name = serializers.CharField(max_length=255, required=False)
    npn = _npn_field(required=True)

    def validate(self, data):
        data = super().validate(data)
        if not (data.get('first_name', '').strip() or data.get('name', '').strip()):
            raise serializers.ValidationError({'first_name': ['Enter the first name.']})
        return data


class AgentUpdateSerializer(_AgentWriteSerializer):
    """Send only the fields that change. A name part sent rebuilds `name`; a
    `name` sent without parts is split into them."""

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
    status = serializers.ChoiceField(
        choices=AGENT_STATUSES,
        required=False,
        help_text='Only agents with this status.',
    )
    state = serializers.CharField(
        required=False,
        allow_blank=True,
        min_length=2,
        max_length=2,
        help_text='Only agents licensed in this state (two-letter code).',
    )
