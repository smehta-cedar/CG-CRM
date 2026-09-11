from django.contrib.auth import password_validation
from rest_framework import serializers

from apps.roles.models import Role

from .models import User


class NestedRoleSerializer(serializers.ModelSerializer):
    """Just enough of the role to label it in the UI."""

    class Meta:
        model = Role
        fields = ['id', 'name']
        read_only_fields = fields


class UserSerializer(serializers.ModelSerializer):
    role = NestedRoleSerializer(read_only=True)
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(),
        source='role',
        write_only=True,
        required=False,
        allow_null=True,
        # PrimaryKeyRelatedField already 404s an id that is not a real role;
        # spell the message the way the frontend wants to show it.
        error_messages={
            'does_not_exist': 'No role with id {pk_value} exists.',
            'incorrect_type': 'Expected a role id, got {data_type}.',
        },
    )
    permissions = serializers.SerializerMethodField()
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
        style={'input_type': 'password'},
    )

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'full_name',
            'role',
            'role_id',
            'permissions',
            'login_type',
            'is_active',
            'is_blocked',
            'is_superuser',
            'must_change_password',
            'password',
            'last_login',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'is_superuser',
            'last_login',
            'created_at',
            'updated_at',
        ]
        extra_kwargs = {
            # is_blocked moves through the block/unblock endpoints, not here,
            # so a general update cannot quietly lock someone out.
            'is_blocked': {'read_only': True},
        }

    def get_permissions(self, obj) -> list:
        """The codenames this account effectively holds.

        Sorted so the response is stable and diffable; superuser-aware, since
        the frontend renders its menus from exactly this list.
        """
        return sorted(obj.permission_codenames)

    def validate_email(self, value):
        email = User.objects.normalize_email(value)
        clashes = User.objects.filter(email__iexact=email)
        if self.instance is not None:
            clashes = clashes.exclude(pk=self.instance.pk)
        if clashes.exists():
            raise serializers.ValidationError(
                'A user with this email address already exists.'
            )
        return email

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User.objects.create_user(password=password, **validated_data)
        if password is None:
            # No password was chosen for them, so there is nothing to sign in
            # with yet; the account waits on a reset rather than being usable.
            user.must_change_password = True
            user.save(update_fields=['must_change_password'])
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        user = super().update(instance, validated_data)
        if password is not None:
            user.set_password(password)
            user.save(update_fields=['password'])
        return user
