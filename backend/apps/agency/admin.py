from django.contrib import admin

from .models import Agency, State

AUDIT_FIELDS = ('created_at', 'updated_at', 'created_by', 'updated_by', 'deleted_at', 'deleted_by')


@admin.register(Agency)
class AgencyAdmin(admin.ModelAdmin):
    list_display = ('name', 'npn', 'email', 'phone', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'aliases', 'npn', 'email', 'phone')
    readonly_fields = AUDIT_FIELDS


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'search_key', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'search_key')
    readonly_fields = AUDIT_FIELDS
