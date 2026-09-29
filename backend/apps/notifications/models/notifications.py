from django.conf import settings
from django.db import models

from apps.base.models import BaseModel
from apps.requests.models import Request


class Notification(BaseModel):
    """One message for one user, shown under the navbar's bell. Filing a
    request sends one to every admin (apps.notifications.services)."""

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    # What it is about, when it is about a request.
    request = models.ForeignKey(Request, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    # App path the notification opens, e.g. "/hr".
    link = models.CharField(max_length=255, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        # Newest first: the bell lists the latest at the top.
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.recipient} - {self.title}'
