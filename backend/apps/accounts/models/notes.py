from django.conf import settings
from django.db import models

from apps.base.models import BaseModel


class UserNote(BaseModel):
    """One change-log entry for a user account, written by the API on
    create, on an update that changed something, on block / unblock and on
    a password set. Append-only.

    `changes` is a list of {"field", "from", "to"} with display strings: the
    role by name, the status as "active" / "inactive". A password change is
    {"field": "password", "from": "", "to": "", "redacted": true}, never with
    a value. `created_by` (from BaseModel) is who made the change.
    """

    KIND_ADDED = 'added'
    KIND_EDITED = 'edited'
    KIND_CHOICES = (
        (KIND_ADDED, 'Added'),
        (KIND_EDITED, 'Edited'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notes')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    changes = models.JSONField(default=list)

    class Meta(BaseModel.Meta):
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.user} - {self.kind}'
