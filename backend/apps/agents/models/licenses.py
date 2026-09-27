from django.db import models

from apps.agency.models import State
from apps.base.models import BaseModel

from .agents import Agent

# active: licence in force. review: renewal or paperwork under review.
# pending: applied for, not issued yet. jit: "just in time", obtained only
# when a sale there needs it.
LICENSE_STATUSES = (
    ('active', 'Active'),
    ('review', 'Review'),
    ('pending', 'Pending'),
    ('jit', 'JIT'),
)


class AgentStateLicense(BaseModel):
    """One agent's licence in one state: the number the state issued, its
    status and its term. Every row counts as a licensed state whatever its
    status; the number is blank until the state issues one.

    These rows are where an agent's licensed states come from: the API
    derives `licensed_states` / `license_numbers` from them and the agent
    form edits them (a checked state keeps or gets a row, an unchecked one
    loses it).
    """

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='licenses')
    state = models.ForeignKey(State, on_delete=models.PROTECT, related_name='agent_licenses')
    license_number = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=10, choices=LICENSE_STATUSES, default='active')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

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
        super().save(*args, **kwargs)
