from rest_framework import serializers

from apps.agency.models import LICENSE_STATUSES, Agency, AgencyNote, AgencyStateLicense
from apps.agency.utils import normalize_aliases


class AgencyLicenseSerializer(serializers.ModelSerializer):
    """One licence row as it appears on the agency."""

    state = serializers.CharField(source='state.code', read_only=True)
    status = serializers.ChoiceField(choices=LICENSE_STATUSES, read_only=True)

    class Meta:
        model = AgencyStateLicense
        fields = ('id', 'state', 'license_number', 'status', 'start_date', 'end_date')
        read_only_fields = fields


class AgencySerializer(serializers.ModelSerializer):
    """How an agency appears in every response."""

    aliases = serializers.ListField(child=serializers.CharField(), read_only=True)
    licenses = serializers.SerializerMethodField(help_text='Licence rows, in state-code order.')

    class Meta:
        model = Agency
        fields = (
            'id',
            'name',
            'aliases',
            'npn',
            'email',
            'phone',
            'licenses',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_licenses(self, agency) -> list:
        rows = sorted(agency.licenses.all(), key=lambda row: row.state.code)
        return AgencyLicenseSerializer(rows, many=True).data


class AgencyChangeSerializer(serializers.Serializer):
    """One changed field in a note: {"field", "from", "to"}, values as shown."""

    field = serializers.CharField()
    to = serializers.CharField(allow_blank=True)

    def get_fields(self):
        # "from" is a Python keyword, so it can't be declared on the class.
        fields = super().get_fields()
        fields['from'] = serializers.CharField(allow_blank=True)
        return fields


class AgencyNoteSerializer(serializers.ModelSerializer):
    """One change-log entry."""

    agency_id = serializers.UUIDField(read_only=True)
    changes = AgencyChangeSerializer(many=True, read_only=True)
    created_by = serializers.SerializerMethodField(help_text='The full name of who made the change.')

    class Meta:
        model = AgencyNote
        fields = ('id', 'agency_id', 'kind', 'changes', 'created_by', 'created_at')
        read_only_fields = fields

    def get_created_by(self, note) -> str | None:
        user = note.created_by
        return user.full_name if user else None


class AgencyLicenseInputSerializer(serializers.Serializer):
    state = serializers.CharField(min_length=2, max_length=2, help_text='Two-letter state code.')
    license_number = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    status = serializers.ChoiceField(
        choices=LICENSE_STATUSES,
        required=False,
        allow_null=True,
        default=None,
        help_text='Left out or null: a new row is active and a kept row keeps its status.',
    )
    start_date = serializers.DateField(
        required=False,
        allow_null=True,
        default=None,
        help_text='Left out or null: a new row starts today and a kept row keeps its date.',
    )
    end_date = serializers.DateField(
        required=False,
        allow_null=True,
        default=None,
        help_text='Left out or null: a new row runs two years from its start and a kept row keeps its date.',
    )

    def validate(self, data):
        start, end = data.get('start_date'), data.get('end_date')
        if start and end and end < start:
            raise serializers.ValidationError({'end_date': ['The end date must be on or after the start date.']})
        return data


def _licenses_field():
    return serializers.ListField(
        child=AgencyLicenseInputSerializer(),
        required=False,
        help_text='The licensed states with their numbers, statuses and dates; replaces the current set.',
    )


def _aliases_field():
    # Blank entries are allowed in, then dropped by normalize_aliases.
    return serializers.ListField(
        child=serializers.CharField(max_length=255, allow_blank=True),
        required=False,
        help_text='Other names the agency goes by.',
    )


def _npn_field():
    # An NPN is up to 10 digits; the model column leaves room for more.
    return serializers.RegexField(
        r'^\d{1,10}$',
        required=False,
        allow_blank=True,
        error_messages={'invalid': 'NPN must be 1 to 10 digits.'},
    )


class AgencyCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    aliases = _aliases_field()
    npn = _npn_field()
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    licenses = _licenses_field()
    is_active = serializers.BooleanField(required=False)

    def validate_aliases(self, value):
        return normalize_aliases(value)


class AgencyUpdateSerializer(serializers.Serializer):
    """Send only the fields that change."""

    name = serializers.CharField(max_length=255, required=False)
    aliases = _aliases_field()
    npn = _npn_field()
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    licenses = _licenses_field()
    is_active = serializers.BooleanField(required=False)

    def validate_aliases(self, value):
        return normalize_aliases(value)


class AgencyListQuerySerializer(serializers.Serializer):
    search = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Matches name, alias, NPN, email or phone.',
    )
    is_active = serializers.BooleanField(
        required=False,
        allow_null=True,
        help_text='true for operating agencies, false for switched-off ones.',
    )
