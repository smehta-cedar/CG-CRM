from django.contrib import admin

from .models import Request

AUDIT_FIELDS = ('created_at', 'updated_at', 'created_by', 'updated_by', 'deleted_at', 'deleted_by')


@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    list_display = ('type', 'who', 'status', 'created_at')
    list_filter = ('type', 'status')
    search_fields = ('agent__name', 'carrier__name', 'buyer_name', 'email', 'note')
    autocomplete_fields = ('agent', 'carrier', 'state')
    readonly_fields = AUDIT_FIELDS

    @admin.display(description='Who')
    def who(self, request):
        return request.buyer_name if request.type == 'merch' else (request.agent.name if request.agent else '')
