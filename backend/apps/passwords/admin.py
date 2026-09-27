from django.contrib import admin

from .models import Password, PasswordNote

AUDIT_FIELDS = ('created_at', 'updated_at', 'created_by', 'updated_by', 'deleted_at', 'deleted_by')


class PasswordNoteInline(admin.TabularInline):
    model = PasswordNote
    extra = 0
    can_delete = False
    readonly_fields = ('kind', 'changes', 'created_at', 'created_by')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Password)
class PasswordAdmin(admin.ModelAdmin):
    list_display = ('agent', 'carrier', 'username', 'status', 'created_at')
    list_filter = ('status', 'carrier')
    search_fields = ('agent__name', 'carrier__name', 'username')
    autocomplete_fields = ('agent', 'carrier')
    readonly_fields = AUDIT_FIELDS
    inlines = (PasswordNoteInline,)


@admin.register(PasswordNote)
class PasswordNoteAdmin(admin.ModelAdmin):
    list_display = ('password', 'kind', 'created_at', 'created_by')
    list_filter = ('kind',)
    search_fields = ('password__agent__name', 'password__carrier__name')
    readonly_fields = ('password', 'kind', 'changes', *AUDIT_FIELDS)
