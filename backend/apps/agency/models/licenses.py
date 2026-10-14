from django.db import models
from django.utils import timezone

from apps.base.models import BaseModel

from .agencies import Agency
from .states import State

# An agent's licence (apps.agents.models.LICENSE_STATUSES) shares the first
# four; the agency's also offers cancelled. Kept here so the agency app does
# not import the agents app. expired is set from the end date on save and
# reported from it on read (current_status).
LICENSE_STATUSES = (
    ('active', 'Active'),
    ('pending', 'Pending'),
    ('applied', 'Applied'),
    ('expired', 'Expired'),
    ('cancelled', 'Cancelled'),
)


class AgencyStateLicense(BaseModel):
    """The agency's licence in one state: the number the state issued, its
    status and its term. Every row counts as a licensed state whatever its
    status; the number is blank until the state issues one.

    The API derives the agency's `licensed_states` / `license_numbers` from
    these rows and the agency form edits them (a checked state keeps or gets
    a row, an unchecked one loses it).

    `life` and `health` are the lines of business the licence covers in that
    state, ticked on the licence form beside the state's number. Both start
    off; the form records what the licence actually covers.
    """

    agency = models.ForeignKey(Agency, on_delete=models.CASCADE, related_name='licenses')
    state = models.ForeignKey(State, on_delete=models.PROTECT, related_name='agency_licenses')
    license_number = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=10, choices=LICENSE_STATUSES, default='active')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    life = models.BooleanField(default=False, help_text='The licence covers life insurance.')
    health = models.BooleanField(default=False, help_text='The licence covers health insurance.')

    @property
    def current_status(self):
        """The status as of today: a row whose end date passed since it was
        saved reads as expired."""
        if self.end_date and self.end_date < timezone.localdate():
            return 'expired'
        return self.status

    @property
    def lines_text(self):
        """"Life & Health", "Life", "Health" or "", as notes show it."""
        lines = [name for flag, name in ((self.life, 'Life'), (self.health, 'Health')) if flag]
        return ' & '.join(lines)

    class Meta(BaseModel.Meta):
        ordering = ('created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=['agency', 'state'],
                condition=models.Q(deleted_at__isnull=True),
                name='uniq_agency_state_license_alive',
                violation_error_message='This agency already has a licence in this state.',
            ),
        ]

    def __str__(self):
        return f'{self.agency} - {self.state.code}'

    def save(self, *args, **kwargs):
        self.license_number = self.license_number.strip()
        if self.end_date and self.end_date < timezone.localdate():
            self.status = 'expired'
        # The status follows the end date, so it is saved whenever the date is.
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and 'end_date' in update_fields and 'status' not in update_fields:
            kwargs['update_fields'] = [*update_fields, 'status']
        super().save(*args, **kwargs)
