from rest_framework import serializers

from apps.accounts.models import Designation, Role, User
from apps.accounts.selectors.designation_selector import DesignationSelector
from apps.accounts.selectors.role_selector import RoleSelector


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

    role = RoleSummarySerializer(read_only=True)
    designation = DesignationSummarySerializer(read_only=True)

    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'full_name',
            'phone',
            'role',
            'designation',
            'is_active',
            'is_superuser',
            'last_login',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


# Only live, active roles and designations can be assigned. The querysets are
# lazy and re-run on every request.
def _role_id_field():
    return serializers.PrimaryKeyRelatedField(
        source='role',
        queryset=RoleSelector().active().get_queryset(),
        pk_field=serializers.UUIDField(),
        required=False,
        allow_null=True,
    )


def _designation_id_field():
    return serializers.PrimaryKeyRelatedField(
        source='designation',
        queryset=DesignationSelector().active().get_queryset(),
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
    role_id = _role_id_field()
    designation_id = _designation_id_field()


class UserUpdateSerializer(serializers.Serializer):
    """Send only the fields that change."""

    email = serializers.EmailField(required=False)
    full_name = serializers.CharField(max_length=255, required=False)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    role_id = _role_id_field()
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
        help_text='Matches email, full name, phone, role or designation.',
    )
    role_id = serializers.UUIDField(required=False)
    designation_id = serializers.UUIDField(required=False)
    is_active = serializers.BooleanField(
        required=False,
        allow_null=True,
        help_text='true for active users, false for blocked ones.',
    )
