from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import (
    AdminPasswordChangeForm,
    AdminUserCreationForm,
    UserChangeForm,
)
from django.utils.translation import gettext_lazy as _

from .models import User


class UserCreationForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ('email', 'full_name')


class UserUpdateForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = UserCreationForm
    form = UserUpdateForm
    change_password_form = AdminPasswordChangeForm
    model = User

    list_display = ('email', 'full_name', 'login_type', 'is_active', 'is_blocked', 'is_staff')
    list_filter = ('is_active', 'is_blocked', 'is_staff', 'is_superuser', 'login_type', 'groups')
    search_fields = ('email', 'full_name')
    ordering = ('full_name', 'email')
    readonly_fields = ('last_login', 'created_at', 'updated_at')
    filter_horizontal = ('groups', 'user_permissions')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('full_name',)}),
        (_('Access'), {
            'fields': (
                'login_type',
                'is_active',
                'is_blocked',
                'must_change_password',
            ),
        }),
        (_('Permissions'), {
            'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'created_at', 'updated_at')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'usable_password', 'password1', 'password2'),
        }),
    )
