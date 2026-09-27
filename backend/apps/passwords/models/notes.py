from django.db import models

from apps.base.models import BaseModel

from .passwords import Password


class PasswordNote(BaseModel):
    """One change-log entry for a password, written by the API on every
    create and on every update that changed something. Append-only.

    `changes` is a list of {"field", "from", "to"} with display strings:
    the agent and carrier by name. The portal password is recorded as
    {"field": "password", "from": "", "to": "", "redacted": true}, never
    with its value. `created_by` (from BaseModel) is who made the change.
    """

    KIND_ADDED = 'added'
    KIND_EDITED = 'edited'
    KIND_CHOICES = (
        (KIND_ADDED, 'Added'),
        (KIND_EDITED, 'Edited'),
    )

    password = models.ForeignKey(Password, on_delete=models.CASCADE, related_name='notes')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    changes = models.JSONField(default=list)

    class Meta(BaseModel.Meta):
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.password} - {self.kind}'
