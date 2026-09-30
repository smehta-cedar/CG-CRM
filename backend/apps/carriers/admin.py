from django.contrib import admin

from .models import Carrier, CarrierNote, CarrierStateLicense

AUDIT_FIELDS = ('created_at', 'updated_at', 'created_by', 'updated_by', 'deleted_at', 'deleted_by')


class CarrierNoteInline(admin.TabularInline):
    model = CarrierNote
    extra = 0
    can_delete = False
    readonly_fields = ('kind', 'changes', 'created_at', 'created_by')

    def has_add_permission(self, request, obj=None):
        return False


class CarrierStateLicenseInline(admin.TabularInline):
    model = CarrierStateLicense
    extra = 0
    fields = ('state', 'license_number', 'status', 'start_date', 'end_date', 'life', 'health')


@admin.register(Carrier)
class CarrierAdmin(admin.ModelAdmin):
    list_display = ('name', 'lines', 'states', 'status', 'created_at')
    list_filter = ('status', 'available_states')
    search_fields = ('name', 'aliases', 'lines_of_business')
    filter_horizontal = ('available_states',)
    # Follows status on save.
    readonly_fields = ('is_active', *AUDIT_FIELDS)
    inlines = (CarrierStateLicenseInline, CarrierNoteInline)

    @admin.display(description='Lines of business')
    def lines(self, carrier):
        return ', '.join(carrier.lines_of_business)

    @admin.display(description='States')
    def states(self, carrier):
        return ', '.join(carrier.state_codes)


@admin.register(CarrierNote)
class CarrierNoteAdmin(admin.ModelAdmin):
    list_display = ('carrier', 'kind', 'created_at', 'created_by')
    list_filter = ('kind',)
    search_fields = ('carrier__name',)
    readonly_fields = ('carrier', 'kind', 'changes', *AUDIT_FIELDS)
