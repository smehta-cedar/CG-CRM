from django.db import models

from apps.base.models import BaseModel

from .agencies import Agency


class AgencyComment(BaseModel):
    """A note someone wrote on the agency: free text, shown on the profile's
    Notes panel newest first. Not the change log (AgencyNote, shown as
    History). `created_by` (from BaseModel) is who wrote it; a deleted one is
    soft-deleted.
    """

    agency = models.ForeignKey(Agency, on_delete=models.CASCADE, related_name='comments')
    body = models.TextField()

    class Meta(BaseModel.Meta):
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.agency} - {self.body[:40]}'

    def save(self, *args, **kwargs):
        self.body = self.body.strip()
        super().save(*args, **kwargs)
