from django.db import models

from apps.base.models import BaseModel

from .agencies import Agency
from .states import State

# An agent's licence (apps.agents.models.LICENSE_STATUSES) shares the first
# three and JIT; the agency's form also offers applied, expired and
# cancelled. Kept here so the agency app does not import the agents app.
LICENSE_STATUSES = (
    ('active', 'Active'),
    ('review', 'Review'),
    ('pending', 'Pending'),
    ('applied', 'Applied'),
    ('expired', 'Expired'),
    ('cancelled', 'Cancelled'),
    ('jit', 'JIT'),
)


class AgencyStateLicense(BaseModel):
    """The agency's licence in one state: the number the state issued, its
    status and its term. Every row counts as a licensed state whatever its
    status; the number is blank until the state issues one.

    The API derives the agency's `licensed_states` / `license_numbers` from
    these rows and the agency form edits them (a checked state keeps or gets
    a row, an unchecked one loses it).
    """

    agency = models.ForeignKey(Agency, on_delete=models.CASCADE, related_name='licenses')
    state = models.ForeignKey(State, on_delete=models.PROTECT, related_name='agency_licenses')
    license_number = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=10, choices=LICENSE_STATUSES, default='active')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

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
        super().save(*args, **kwargs)
