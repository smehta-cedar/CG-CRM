from django.contrib import admin

from .models import (
    CarrierPolicy,
    CarrierPolicyNote,
    Certification,
    CertificationNote,
    PolicyType,
    PolicyTypeNote,
)

AUDIT_FIELDS = ('created_at', 'updated_at', 'created_by', 'updated_by', 'deleted_at', 'deleted_by')


class PolicyTypeNoteInline(admin.TabularInline):
    model = PolicyTypeNote
    extra = 0
    can_delete = False
    readonly_fields = ('kind', 'changes', 'created_at', 'created_by')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PolicyType)
class PolicyTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)
    readonly_fields = AUDIT_FIELDS
    inlines = (PolicyTypeNoteInline,)


@admin.register(PolicyTypeNote)
class PolicyTypeNoteAdmin(admin.ModelAdmin):
    list_display = ('policy_type', 'kind', 'created_at', 'created_by')
    list_filter = ('kind',)
    search_fields = ('policy_type__name',)
    readonly_fields = ('policy_type', 'kind', 'changes', *AUDIT_FIELDS)


class CarrierPolicyNoteInline(admin.TabularInline):
    model = CarrierPolicyNote
    extra = 0
    can_delete = False
    readonly_fields = ('kind', 'changes', 'created_at', 'created_by')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CarrierPolicy)
class CarrierPolicyAdmin(admin.ModelAdmin):
    list_display = ('name', 'carrier', 'policy_type', 'states', 'is_active', 'created_at')
    list_filter = ('is_active', 'policy_type', 'carrier')
    search_fields = ('name', 'carrier__name', 'policy_type__name')
    filter_horizontal = ('available_states',)
    readonly_fields = AUDIT_FIELDS
    inlines = (CarrierPolicyNoteInline,)

    @admin.display(description='Available states')
    def states(self, policy):
        return ', '.join(policy.state_codes)


@admin.register(CarrierPolicyNote)
class CarrierPolicyNoteAdmin(admin.ModelAdmin):
    list_display = ('policy', 'kind', 'created_at', 'created_by')
    list_filter = ('kind',)
    search_fields = ('policy__name', 'policy__carrier__name')
    readonly_fields = ('policy', 'kind', 'changes', *AUDIT_FIELDS)


class CertificationNoteInline(admin.TabularInline):
    model = CertificationNote
    extra = 0
    can_delete = False
    readonly_fields = ('kind', 'changes', 'created_at', 'created_by')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Certification)
class CertificationAdmin(admin.ModelAdmin):
    list_display = ('agent', 'carrier', 'line_of_business', 'due_date', 'is_verified', 'is_active', 'created_at')
    list_filter = ('is_active', 'is_verified', 'line_of_business', 'carrier')
    search_fields = ('agent__name', 'carrier__name')
    # The PDF sits in private storage with no URL, so the admin shows its name only.
    exclude = ('file',)
    readonly_fields = ('file_name', *AUDIT_FIELDS)
    inlines = (CertificationNoteInline,)


@admin.register(CertificationNote)
class CertificationNoteAdmin(admin.ModelAdmin):
    list_display = ('certification', 'kind', 'created_at', 'created_by')
    list_filter = ('kind',)
    search_fields = ('certification__agent__name', 'certification__carrier__name')
    readonly_fields = ('certification', 'kind', 'changes', *AUDIT_FIELDS)
