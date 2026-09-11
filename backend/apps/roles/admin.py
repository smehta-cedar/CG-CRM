from django.contrib import admin

from .models import Permission, Role


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('codename', 'module', 'resource', 'action')
    list_filter = ('module', 'resource')
    search_fields = ('codename', 'module', 'resource', 'action')
    ordering = ('module', 'resource', 'id')

    # The catalog is owned by apps/roles/catalog.py and `seed_permissions`;
    # hand-editing rows here would drift from it.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'user_count', 'created_at')
    search_fields = ('name',)
    filter_horizontal = ('permissions',)
    ordering = ('name',)

    @admin.display(description='users')
    def user_count(self, obj):
        return obj.users.count()
