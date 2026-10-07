from rest_framework import serializers

from apps.accounts.models import Designation, Role, User, UserNote
from apps.accounts.models.roles import ACTIONS, PERMISSION_LABELS


class RoleSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ('id', 'name')


class DesignationSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Designation
        fields = ('id', 'name')


class UserSerializer(serializers.ModelSerializer):
    """How a user appears in every response."""

    roles = RoleSummarySerializer(many=True, read_only=True)
    designation = DesignationSummarySerializer(read_only=True)
    agent_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'full_name',
            'phone',
            'roles',
            'designation',
            'agent_id',
            'is_active',
            'is_superuser',
            'last_login',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class MeSerializer(UserSerializer):
    """The signed-in user, plus what their roles let them do (GET /auth/me/).

    `permissions` maps each module code they can do anything on to its
    action flags: {"agents": {"view": true, "create": false, ...}, ...}.
    Built from User.has_permission, so a superuser has every module, and an
    agent's account or a blocked user only what that check allows.
    """

    permissions = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = (*UserSerializer.Meta.fields, 'permissions')
        read_only_fields = fields

    def get_permissions(self, user) -> dict[str, dict[str, bool]]:
        permissions = {}
        for module in PERMISSION_LABELS:
            flags = {action: user.has_permission(module, action) for action in ACTIONS}
            if any(flags.values()):
                permissions[module] = flags
        return permissions


class UserChangeSerializer(serializers.Serializer):
    """One changed field in a note: {"field", "from", "to", "redacted"?}."""

    field = serializers.CharField()
    to = serializers.CharField(allow_blank=True)
    redacted = serializers.BooleanField(required=False)

    def get_fields(self):
        # "from" is a Python keyword, so it can't be declared on the class.
        fields = super().get_fields()
        fields['from'] = serializers.CharField(allow_blank=True)
        return fields


class UserNoteSerializer(serializers.ModelSerializer):
    """One change-log entry."""

    user_id = serializers.UUIDField(read_only=True)
    changes = UserChangeSerializer(many=True, read_only=True)
    created_by = serializers.SerializerMethodField(help_text='The full name of who made the change.')

    class Meta:
        model = UserNote
        fields = ('id', 'user_id', 'kind', 'changes', 'created_by', 'created_at')
        read_only_fields = fields

    def get_created_by(self, note) -> str | None:
        user = note.created_by
        return user.full_name if user else None


# Only live, active roles and designations can be assigned. The querysets are
# lazy and re-run on every request.
def _role_ids_field():
    """The full list of roles; [] for none. Sent ids replace the user's roles."""
    return serializers.PrimaryKeyRelatedField(
        source='roles',
        queryset=Role.objects.filter(is_active=True),
        pk_field=serializers.UUIDField(),
        many=True,
        required=False,
    )


def _designation_id_field():
    return serializers.PrimaryKeyRelatedField(
        source='designation',
        queryset=Designation.objects.filter(is_active=True),
        pk_field=serializers.UUIDField(),
        required=False,
        allow_null=True,
    )


def _password_field():
    return serializers.CharField(write_only=True, trim_whitespace=False, style={'input_type': 'password'})


class UserCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=255)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    password = _password_field()
    role_ids = _role_ids_field()
    designation_id = _designation_id_field()


class UserUpdateSerializer(serializers.Serializer):
    """Send only the fields that change."""

    email = serializers.EmailField(required=False)
    full_name = serializers.CharField(max_length=255, required=False)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    role_ids = _role_ids_field()
    designation_id = _designation_id_field()


class SetPasswordSerializer(serializers.Serializer):
    new_password = _password_field()
    confirm_password = _password_field()

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        return attrs


class UserListQuerySerializer(serializers.Serializer):
    search = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Matches email, full name, phone, any role or designation.',
    )
    role_id = serializers.UUIDField(required=False, help_text='Users holding this role, among others.')
    designation_id = serializers.UUIDField(required=False)
    is_active = serializers.BooleanField(
        required=False,
        allow_null=True,
        help_text='true for active users, false for blocked ones.',
    )
