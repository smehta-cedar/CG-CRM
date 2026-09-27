from django.contrib import admin

from .models import AgencyCarrierContract, AgencyCarrierContractNote, CarrierContract, CarrierContractNote

AUDIT_FIELDS = ('created_at', 'updated_at', 'created_by', 'updated_by', 'deleted_at', 'deleted_by')


class CarrierContractNoteInline(admin.TabularInline):
    model = CarrierContractNote
    extra = 0
    can_delete = False
    readonly_fields = ('kind', 'changes', 'created_at', 'created_by')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CarrierContract)
class CarrierContractAdmin(admin.ModelAdmin):
    list_display = ('agent', 'carrier', 'writing_number', 'states', 'created_at')
    list_filter = ('carrier',)
    search_fields = ('agent__name', 'carrier__name', 'writing_number')
    autocomplete_fields = ('agent', 'carrier')
    filter_horizontal = ('appointed_states',)
    readonly_fields = AUDIT_FIELDS
    inlines = (CarrierContractNoteInline,)

    @admin.display(description='States')
    def states(self, contract):
        return ', '.join(contract.state_codes)


@admin.register(CarrierContractNote)
class CarrierContractNoteAdmin(admin.ModelAdmin):
    list_display = ('contract', 'kind', 'created_at', 'created_by')
    list_filter = ('kind',)
    search_fields = ('contract__agent__name', 'contract__carrier__name')
    readonly_fields = ('contract', 'kind', 'changes', *AUDIT_FIELDS)


class AgencyCarrierContractNoteInline(admin.TabularInline):
    model = AgencyCarrierContractNote
    extra = 0
    can_delete = False
    readonly_fields = ('kind', 'changes', 'created_at', 'created_by')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(AgencyCarrierContract)
class AgencyCarrierContractAdmin(admin.ModelAdmin):
    list_display = ('carrier', 'agency', 'contract_number', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('carrier__name', 'agency__name', 'contract_number')
    autocomplete_fields = ('agency', 'carrier')
    filter_horizontal = ('policies',)
    readonly_fields = AUDIT_FIELDS
    inlines = (AgencyCarrierContractNoteInline,)


@admin.register(AgencyCarrierContractNote)
class AgencyCarrierContractNoteAdmin(admin.ModelAdmin):
    list_display = ('contract', 'kind', 'created_at', 'created_by')
    list_filter = ('kind',)
    search_fields = ('contract__carrier__name',)
    readonly_fields = ('contract', 'kind', 'changes', *AUDIT_FIELDS)
