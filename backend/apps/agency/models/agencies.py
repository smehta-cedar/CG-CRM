from django.db import models
from django.db.models.functions import Lower

from apps.base.models import BaseModel


class Agency(BaseModel):
    """An insurance agency, e.g. "Cedar Grove Senior Health Solutions".

    `is_active` (from BaseModel) is whether it is operating; it starts on.
    """

    name = models.CharField(max_length=255)
    # Other names the agency goes by, e.g. ["Cedar Grove", "CGSHS"].
    aliases = models.JSONField(default=list, blank=True)
    # National Producer Number. Blank when not (yet) known.
    npn = models.CharField('NPN', max_length=20, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)

    class Meta(BaseModel.Meta):
        verbose_name_plural = 'agencies'
        constraints = [
            # Case-insensitive, and a deleted agency's name can be reused.
            models.UniqueConstraint(
                Lower('name'),
                condition=models.Q(deleted_at__isnull=True),
                name='uniq_agency_name_alive',
                violation_error_message='An agency with this name already exists.',
            ),
            # Blank NPNs are not unique; a deleted agency's NPN can be reused.
            models.UniqueConstraint(
                fields=['npn'],
                condition=models.Q(deleted_at__isnull=True) & ~models.Q(npn=''),
                name='uniq_agency_npn_alive',
                violation_error_message='An agency with this NPN already exists.',
            ),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = ' '.join(self.name.split())
        self.npn = self.npn.strip()
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)
