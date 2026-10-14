from django.db import models
from django.utils import timezone

from apps.agency.models import State
from apps.base.models import BaseModel

from .agents import Agent

# active: licence in force. applied: the application is in. pending: applied
# for, not issued yet. expired: the end date has passed (set from the date on
# save, and reported from it on read; see current_status).
LICENSE_STATUSES = (
    ('active', 'Active'),
    ('applied', 'Applied'),
    ('pending', 'Pending'),
    ('expired', 'Expired'),
)



class AgentStateLicense(BaseModel):
    """One agent's licence in one state: the number the state issued, its
    status and its term. Every row counts as a licensed state whatever its
    status; the number is blank until the state issues one.

    These rows are where an agent's licensed states come from: the API
    derives `licensed_states` / `license_numbers` from them and the agent
    form edits them (a checked state keeps or gets a row, an unchecked one
    loses it).

    `life` and `health` are the lines of business the licence covers in that
    state, ticked on the agent form beside the state's number. Both start
    off; the form records what the licence actually covers.
    """

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='licenses')
    state = models.ForeignKey(State, on_delete=models.PROTECT, related_name='agent_licenses')
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
                fields=['agent', 'state'],
                condition=models.Q(deleted_at__isnull=True),
                name='uniq_agent_state_license_alive',
                violation_error_message='This agent already has a licence in this state.',
            ),
        ]

    def __str__(self):
        return f'{self.agent} - {self.state.code}'

    def save(self, *args, **kwargs):
        self.license_number = self.license_number.strip()
        if self.end_date and self.end_date < timezone.localdate():
            self.status = 'expired'
        # The status follows the end date, so it is saved whenever the date is.
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and 'end_date' in update_fields and 'status' not in update_fields:
            kwargs['update_fields'] = [*update_fields, 'status']
        super().save(*args, **kwargs)
