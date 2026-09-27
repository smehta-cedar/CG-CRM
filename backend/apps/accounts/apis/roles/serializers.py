from rest_framework import serializers

from apps.accounts.models import Role, RolePermission
from apps.accounts.models.roles import ACTIONS, PERMISSION_LABELS


class ModuleSerializer(serializers.Serializer):
    """One screen a role can be granted, as the Roles page lists them."""

    code = serializers.CharField()
    label = serializers.CharField()


class RolePermissionSerializer(serializers.ModelSerializer):
    """What a role may do on one module. Sent and returned in the same shape."""

    module = serializers.ChoiceField(choices=[(code, label) for code, label in PERMISSION_LABELS.items()])

    class Meta:
        model = RolePermission
        fields = ('module', 'can_view', 'can_create', 'can_update', 'can_delete')
        extra_kwargs = {f'can_{action}': {'required': False, 'default': False} for action in ACTIONS}

    def validate(self, attrs):
        if any(attrs.get(f'can_{action}') for action in ('create', 'update', 'delete')) and not attrs.get('can_view'):
            raise serializers.ValidationError('Create, update or delete also needs view.')
        return attrs


class RoleSerializer(serializers.ModelSerializer):
    """How a role appears in every response: its permissions and how many live users hold it."""

    permissions = RolePermissionSerializer(many=True, read_only=True)
    user_count = serializers.IntegerField(read_only=True, help_text='Live users assigned this role.')

    class Meta:
        model = Role
        fields = ('id', 'name', 'description', 'is_active', 'permissions', 'user_count', 'created_at', 'updated_at')
        read_only_fields = fields


def _permissions_field(**kwargs):
    return RolePermissionSerializer(many=True, help_text='One entry per module; a module left out gets no access.', **kwargs)


def _ensure_unique_modules(permissions):
    seen = set()
    for permission in permissions:
        module = permission['module']
        if module in seen:
            raise serializers.ValidationError({'permissions': [f'Module {module!r} is listed more than once.']})
        seen.add(module)
    return permissions


class RoleCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False, default=True)
    permissions = _permissions_field(required=False, default=list)

    def validate_permissions(self, permissions):
        return _ensure_unique_modules(permissions)


class RoleUpdateSerializer(serializers.Serializer):
    """Send only the fields that change. `permissions` replaces the whole set."""

    name = serializers.CharField(max_length=100, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    permissions = _permissions_field(required=False)

    def validate_permissions(self, permissions):
        return _ensure_unique_modules(permissions)


class RoleListQuerySerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True, help_text='Matches name or description.')
    is_active = serializers.BooleanField(
        required=False,
        allow_null=True,
        help_text='true for active roles, false for inactive ones; leave out for all.',
    )
