from django.db import models
from django.db.models.functions import Lower

from apps.base.models import BaseModel

# Where the agent stands with the agency. Every status but inactive counts as
# active (is_active), so onboarding and SDR agents can still sign in.
AGENT_STATUSES = (
    ('active', 'Active'),
    ('onboarding', 'Onboarding'),
    ('sdr', 'SDR'),
    ('inactive', 'Inactive'),
)


def split_name(name):
    """("First and middle words", "Last") from a full name; one word is a first name only."""
    words = name.split()
    if len(words) < 2:
        return ' '.join(words), ''
    return ' '.join(words[:-1]), words[-1]


class Agent(BaseModel):
    """A licensed insurance agent under the agency, e.g. "Maria Alva".

    Email and phone are the work contact; the personal_* and address_*
    columns are the agent's own, all optional, as are the dates and
    ssn_last4. Licensed states live on
    AgentStateLicense rows (one per state). Writing numbers live on carrier
    contracts and portal logins on passwords, not here. Sign-in to this app
    is a one-time code emailed to the work email; there is no password.

    `status` is the agent's status (AGENT_STATUSES); `is_active` (from
    BaseModel) follows it, off only for inactive.
    """

    # The full name, "First Last", built from the two parts on save. A middle
    # name, if any, is part of first_name.
    name = models.CharField(max_length=255)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
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
    status = models.CharField(max_length=10, choices=AGENT_STATUSES, default='active')
    # Free-text notes about the agent, shown as "Notes". Not the change log,
    # which is AgentNote (related_name "notes", hence this name).
    remarks = models.TextField(blank=True)

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
        for field in ('first_name', 'last_name'):
            setattr(self, field, ' '.join(getattr(self, field).split()))
        if self.first_name or self.last_name:
            self.name = ' '.join(part for part in (self.first_name, self.last_name) if part)
        else:
            # Only a full name given (older callers, the seed): split it.
            self.name = ' '.join(self.name.split())
            self.first_name, self.last_name = split_name(self.name)
        self.npn = self.npn.strip()
        for field in ('email', 'personal_email'):
            value = getattr(self, field)
            if value:
                setattr(self, field, value.strip().lower())
        self.address_state = self.address_state.strip().upper()
        self.remarks = self.remarks.strip()
        # status is the source of truth; set it, not is_active.
        self.is_active = self.status != 'inactive'
        super().save(*args, **kwargs)
