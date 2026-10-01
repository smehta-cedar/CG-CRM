from rest_framework import serializers

from apps.policies.models import PolicyType, PolicyTypeNote


class PolicyTypeSerializer(serializers.ModelSerializer):
    """How a policy type appears in every response."""

    class Meta:
        model = PolicyType
        fields = (
            'id',
            'name',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class PolicyTypeChangeSerializer(serializers.Serializer):
    """One changed field in a note: {"field", "from", "to"}, values as shown."""

    field = serializers.CharField()
    to = serializers.CharField(allow_blank=True)

    def get_fields(self):
        # "from" is a Python keyword, so it can't be declared on the class.
        fields = super().get_fields()
        fields['from'] = serializers.CharField(allow_blank=True)
        return fields


class PolicyTypeNoteSerializer(serializers.ModelSerializer):
    """One change-log entry."""

    policy_type_id = serializers.UUIDField(read_only=True)
    changes = PolicyTypeChangeSerializer(many=True, read_only=True)
    created_by = serializers.SerializerMethodField(help_text='The full name of who made the change.')

    class Meta:
        model = PolicyTypeNote
        fields = ('id', 'policy_type_id', 'kind', 'changes', 'created_by', 'created_at')
        read_only_fields = fields

    def get_created_by(self, note) -> str | None:
        user = note.created_by
        return user.full_name if user else None


class PolicyTypeCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    is_active = serializers.BooleanField(required=False)


class PolicyTypeUpdateSerializer(serializers.Serializer):
    """Send only the fields that change."""

    name = serializers.CharField(max_length=255, required=False)
    is_active = serializers.BooleanField(required=False)


class PolicyTypeListQuerySerializer(serializers.Serializer):
    search = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Matches the name.',
    )
    is_active = serializers.BooleanField(
        required=False,
        allow_null=True,
        help_text='true for active policy types, false for inactive ones.',
    )
