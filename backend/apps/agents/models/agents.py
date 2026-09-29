from django.db import models
from django.db.models.functions import Lower

from apps.base.models import BaseModel


class Agent(BaseModel):
    """A licensed insurance agent under the agency, e.g. "Maria Alva".

    Email and phone are the work contact; the personal_* and address_*
    columns are the agent's own, all optional, as are the dates and
    ssn_last4. Licensed states live on
    AgentStateLicense rows (one per state). Writing numbers live on carrier
    contracts and portal logins on passwords, not here.

    `is_active` (from BaseModel) is the agent's status; it starts on.
    """

    name = models.CharField(max_length=255)
    # Other names seen on statements (DBA, nickname, maiden), e.g. ["Jim Carter"].
    aliases = models.JSONField(default=list, blank=True)
    # National Producer Number. Unique among live agents.
    npn = models.CharField('NPN', max_length=20)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)

    personal_email = models.EmailField(blank=True)
    personal_phone = models.CharField(max_length=20, blank=True)
    # Home address, all four parts or none (the API enforces that).
    address_street = models.CharField(max_length=255, blank=True)
    address_city = models.CharField(max_length=100, blank=True)
    address_state = models.CharField(max_length=2, blank=True, help_text='Two-letter USPS code.')
    address_zip = models.CharField(max_length=10, blank=True)

    date_of_birth = models.DateField(null=True, blank=True)
    # When they joined the agency.
    join_date = models.DateField(null=True, blank=True)
    # Employment start; not a licence's start_date.
    start_date = models.DateField(null=True, blank=True)
    # Only ever the last four digits of the SSN, never the full number.
    ssn_last4 = models.CharField('SSN (last 4)', max_length=4, blank=True)

    class Meta(BaseModel.Meta):
        constraints = [
            # Case-insensitive, and a deleted agent's name can be reused.
            models.UniqueConstraint(
                Lower('name'),
                condition=models.Q(deleted_at__isnull=True),
                name='uniq_agent_name_alive',
                violation_error_message='An agent with this name already exists.',
            ),
            # A deleted agent's NPN can be reused.
            models.UniqueConstraint(
                fields=['npn'],
                condition=models.Q(deleted_at__isnull=True),
                name='uniq_agent_npn_alive',
                violation_error_message='An agent with this NPN already exists.',
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def address(self):
        """The address as one dict, or None when no part is filled."""
        if not (self.address_street or self.address_city or self.address_state or self.address_zip):
            return None
        return {
            'street': self.address_street,
            'city': self.address_city,
            'state': self.address_state,
            'zip': self.address_zip,
        }

    def save(self, *args, **kwargs):
        self.name = ' '.join(self.name.split())
        self.npn = self.npn.strip()
        for field in ('email', 'personal_email'):
            value = getattr(self, field)
            if value:
                setattr(self, field, value.strip().lower())
        self.address_state = self.address_state.strip().upper()
        super().save(*args, **kwargs)
