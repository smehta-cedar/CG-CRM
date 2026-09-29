from django.contrib import admin

from .models import Notification

AUDIT_FIELDS = ('created_at', 'updated_at', 'created_by', 'updated_by', 'deleted_at', 'deleted_by')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient', 'read_at', 'created_at')
    list_filter = ('read_at',)
    search_fields = ('title', 'body', 'recipient__email', 'recipient__full_name')
    raw_id_fields = ('recipient', 'request')
    readonly_fields = AUDIT_FIELDS
