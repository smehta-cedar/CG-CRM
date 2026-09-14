from apps.accounts.models import Role, RolePermission
from apps.base.selectors.base import BaseSelector


class RoleSelector(BaseSelector):
    """Roles, and the RolePermission rows that belong to them."""

    model = Role

    def active(self):
        self.queryset = self.queryset.filter(is_active=True)
        return self

    def search(self, value):
        if value:
            self.queryset = self.queryset.filter(name__icontains=value)
        return self

    def with_permissions(self):
        self.queryset = self.queryset.prefetch_related('permissions')
        return self

    def name_taken(self, name, exclude_pk=None):
        # Mirrors uniq_role_name_alive: case-insensitive, live roles only.
        queryset = Role.objects.filter(name__iexact=name.strip())
        if exclude_pk is not None:
            queryset = queryset.exclude(pk=exclude_pk)
        return queryset.exists()

    def user_count(self, role):
        return role.users.count()

    def get_permissions(self, role):
        return RolePermission.objects.filter(role=role)
