from rest_framework import serializers

from apps.agency.models import Agency
from apps.agency.utils import normalize_aliases


class AgencySerializer(serializers.ModelSerializer):
    """How an agency appears in every response."""

    aliases = serializers.ListField(child=serializers.CharField(), read_only=True)

    class Meta:
        model = Agency
        fields = (
            'id',
            'name',
            'aliases',
            'npn',
            'email',
            'phone',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


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
