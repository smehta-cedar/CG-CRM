from django.contrib import admin

from .models import Agency, AgencyNote, AgencyStateLicense, State

AUDIT_FIELDS = ('created_at', 'updated_at', 'created_by', 'updated_by', 'deleted_at', 'deleted_by')


class AgencyStateLicenseInline(admin.TabularInline):
    model = AgencyStateLicense
    extra = 0
    fields = ('state', 'license_number', 'status', 'start_date', 'end_date')
    autocomplete_fields = ('state',)


class AgencyNoteInline(admin.TabularInline):
    model = AgencyNote
    extra = 0
    can_delete = False
    readonly_fields = ('kind', 'changes', 'created_at', 'created_by')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Agency)
class AgencyAdmin(admin.ModelAdmin):
    list_display = ('name', 'npn', 'email', 'phone', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'aliases', 'npn', 'email', 'phone')
    readonly_fields = AUDIT_FIELDS
    inlines = (AgencyStateLicenseInline, AgencyNoteInline)


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'search_key', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'search_key')
    readonly_fields = AUDIT_FIELDS
