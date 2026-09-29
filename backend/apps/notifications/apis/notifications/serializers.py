from rest_framework import serializers

from apps.notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    request_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = Notification
        fields = ('id', 'title', 'body', 'link', 'request_id', 'read_at', 'created_at')
        read_only_fields = fields
