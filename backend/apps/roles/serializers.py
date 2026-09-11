from rest_framework import serializers

from .models import Permission, Role


class PermissionSerializer(serializers.ModelSerializer):
    label = serializers.CharField(read_only=True)

    class Meta:
        model = Permission
        fields = ['id', 'module', 'resource', 'action', 'codename', 'label']
        read_only_fields = fields


class RoleSerializer(serializers.ModelSerializer):
    """Reads back the full permission objects, accepts a list of ids on write."""

    permissions = PermissionSerializer(many=True, read_only=True)
    permission_ids = serializers.PrimaryKeyRelatedField(
        queryset=Permission.objects.all(),
        many=True,
        write_only=True,
        source='permissions',
        # A role with no permissions is legitimate - it is how you park one.
        required=False,
        default=list,
    )
    user_count = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = [
            'id',
            'name',
            'permissions',
            'permission_ids',
            'user_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_user_count(self, obj) -> int:
        # The viewset annotates this so a list costs one query. A just-created
        # or just-updated instance carries no annotation, so fall back.
        annotated = getattr(obj, 'user_count', None)
        return obj.users.count() if annotated is None else annotated

    def validate_name(self, value):
        # The unique constraint is case-sensitive; "Admin" and "admin" are the
        # same role to anyone reading a dropdown.
        name = value.strip()
        if not name:
            raise serializers.ValidationError('This field may not be blank.')

        clashes = Role.objects.filter(name__iexact=name)
        if self.instance is not None:
            clashes = clashes.exclude(pk=self.instance.pk)
        if clashes.exists():
            raise serializers.ValidationError(
                f"A role named '{name}' already exists."
            )
        return name


class RoleDeleteSerializer(serializers.Serializer):
    """Validation-only serializer guarding role deletion.

    Lives here rather than in the view so any caller - the viewset, a bulk
    action, a future admin action - gets the same answer:

        RoleDeleteSerializer.check(role)          # raises ValidationError
        RoleDeleteSerializer.for_role(role).is_valid()
    """

    @classmethod
    def for_role(cls, role):
        # DRF refuses to validate without a `data=`; a delete has no body.
        return cls(instance=role, data={})

    @classmethod
    def check(cls, role):
        cls.for_role(role).is_valid(raise_exception=True)

    def validate(self, attrs):
        role = self.instance
        assigned = role.users.count()
        if assigned:
            # Message only: DRF coerces every value in a ValidationError to a
            # string, so a numeric count would arrive as "3". The real integer
            # is on GET /roles/<id>/ as `user_count`.
            raise serializers.ValidationError({
                'detail': (
                    f'This role is assigned to {assigned} '
                    f'{"user" if assigned == 1 else "users"}.'
                ),
            })
        return attrs
