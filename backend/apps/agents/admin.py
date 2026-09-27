from django.contrib import admin

from .models import Agent, AgentNote, AgentStateLicense

AUDIT_FIELDS = ('created_at', 'updated_at', 'created_by', 'updated_by', 'deleted_at', 'deleted_by')


class AgentStateLicenseInline(admin.TabularInline):
    model = AgentStateLicense
    extra = 0
    fields = ('state', 'license_number', 'life', 'health', 'status', 'start_date', 'end_date')
    autocomplete_fields = ('state',)


class AgentNoteInline(admin.TabularInline):
    model = AgentNote
    extra = 0
    can_delete = False
    readonly_fields = ('kind', 'changes', 'created_at', 'created_by')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('name', 'npn', 'email', 'phone', 'states', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'aliases', 'npn', 'email', 'phone')
    readonly_fields = AUDIT_FIELDS
    inlines = (AgentStateLicenseInline, AgentNoteInline)

    @admin.display(description='Licensed states')
    def states(self, agent):
        return ', '.join(sorted(row.state.code for row in agent.licenses.all()))


@admin.register(AgentStateLicense)
class AgentStateLicenseAdmin(admin.ModelAdmin):
    list_display = ('agent', 'state', 'license_number', 'life', 'health', 'status', 'start_date', 'end_date')
    list_filter = ('status', 'state', 'life', 'health')
    search_fields = ('agent__name', 'license_number')
    readonly_fields = AUDIT_FIELDS


@admin.register(AgentNote)
class AgentNoteAdmin(admin.ModelAdmin):
    list_display = ('agent', 'kind', 'created_at', 'created_by')
    list_filter = ('kind',)
    search_fields = ('agent__name',)
    readonly_fields = ('agent', 'kind', 'changes', *AUDIT_FIELDS)
