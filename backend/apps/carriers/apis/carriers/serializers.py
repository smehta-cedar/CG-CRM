from rest_framework import serializers

from apps.carriers.models import LINES_OF_BUSINESS, Carrier, CarrierNote
from apps.carriers.utils import normalize_aliases, normalize_lines
from apps.contracts.utils import is_agent_accessible


class CarrierSerializer(serializers.ModelSerializer):
    """How a carrier appears in every response."""

    aliases = serializers.ListField(child=serializers.CharField(), read_only=True)
    lines_of_business = serializers.ListField(child=serializers.CharField(), read_only=True)
    available_states = serializers.ListField(
        child=serializers.CharField(),
        source='state_codes',
        read_only=True,
        help_text='Two-letter state codes, in code order.',
    )
    agent_accessible = serializers.SerializerMethodField(
        help_text=(
            "True only when the carrier's live agency contract has a contract number: "
            'agents can be appointed to it and given a portal password there.'
        ),
    )

    class Meta:
        model = Carrier
        fields = (
            'id',
            'name',
            'aliases',
            'lines_of_business',
            'available_states',
            'agent_accessible',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_agent_accessible(self, carrier) -> bool:
        return is_agent_accessible(carrier)


class CarrierChangeSerializer(serializers.Serializer):
    """One changed field in a note: {"field", "from", "to"}, values as shown."""

    field = serializers.CharField()
    to = serializers.CharField(allow_blank=True)

    def get_fields(self):
        # "from" is a Python keyword, so it can't be declared on the class.
        fields = super().get_fields()
        fields['from'] = serializers.CharField(allow_blank=True)
        return fields


class CarrierNoteSerializer(serializers.ModelSerializer):
    """One change-log entry."""

    carrier_id = serializers.UUIDField(read_only=True)
    changes = CarrierChangeSerializer(many=True, read_only=True)
    created_by = serializers.SerializerMethodField(help_text="The full name of who made the change.")

    class Meta:
        model = CarrierNote
        fields = ('id', 'carrier_id', 'kind', 'changes', 'created_by', 'created_at')
        read_only_fields = fields

    def get_created_by(self, note) -> str | None:
        user = note.created_by
        return user.full_name if user else None


def _aliases_field():
    # Blank entries are allowed in, then dropped by normalize_aliases.
    return serializers.ListField(
        child=serializers.CharField(max_length=255, allow_blank=True),
        required=False,
        help_text='Other names the carrier goes by.',
    )


def _lines_field(required):
    return serializers.ListField(
        child=serializers.ChoiceField(choices=LINES_OF_BUSINESS),
        required=required,
        help_text=f"At least one of {', '.join(LINES_OF_BUSINESS)}.",
    )


def _states_field():
    return serializers.ListField(
        child=serializers.CharField(min_length=2, max_length=2),
        required=False,
        help_text='Two-letter state codes the carrier is available in.',
    )


class CarrierCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    aliases = _aliases_field()
    lines_of_business = _lines_field(required=True)
    available_states = _states_field()
    is_active = serializers.BooleanField(required=False)

    def validate_aliases(self, value):
        return normalize_aliases(value)

    def validate_lines_of_business(self, value):
        return normalize_lines(value)


class CarrierUpdateSerializer(serializers.Serializer):
    """Send only the fields that change."""

    name = serializers.CharField(max_length=255, required=False)
    aliases = _aliases_field()
    lines_of_business = _lines_field(required=False)
    available_states = _states_field()
    is_active = serializers.BooleanField(required=False)

    def validate_aliases(self, value):
        return normalize_aliases(value)

    def validate_lines_of_business(self, value):
        return normalize_lines(value)


class CarrierListQuerySerializer(serializers.Serializer):
    search = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Matches name, alias or line of business.',
    )
    is_active = serializers.BooleanField(
        required=False,
        allow_null=True,
        help_text='true for active carriers, false for inactive ones.',
    )
    state = serializers.CharField(
        required=False,
        allow_blank=True,
        min_length=2,
        max_length=2,
        help_text='Only carriers available in this state (two-letter code).',
    )
