from django.db import models

from apps.agency.models import Agency
from apps.agents.models import Agent
from apps.base.models import BaseModel
from apps.carriers.models import Carrier

# active: in use. pending: requested, not confirmed by the carrier yet.
# inactive: no longer used.
PASSWORD_STATUSES = (
    ('active', 'Active'),
    ('pending', 'Pending'),
    ('inactive', 'Inactive'),
)


class Password(BaseModel):
    """One portal login at one carrier: the portal username and password.
    It belongs to an agent or to the agency itself, exactly one of the two.
    Distinct from the app's own sign-in. The writing number (producer ID)
    lives on the carrier contract.

    The portal password is stored as entered so it can be shown and copied;
    access is limited to the `passwords` permission module. `is_active`
    (from BaseModel) is not used; `status` has three values.
    """

    # Exactly one of these is set: an agent's login, or the agency's own.
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='passwords', null=True, blank=True)
    agency = models.ForeignKey(Agency, on_delete=models.CASCADE, related_name='passwords', null=True, blank=True)
    carrier = models.ForeignKey(Carrier, on_delete=models.CASCADE, related_name='passwords')
    username = models.CharField(max_length=255)
    portal_password = models.CharField(max_length=255)
    # The carrier portal's sign-in page. Blank when none.
    link = models.URLField(max_length=2000, blank=True)
    status = models.CharField(max_length=10, choices=PASSWORD_STATUSES, default='active')

    class Meta(BaseModel.Meta):
        constraints = [
            # One password per agent at each carrier; a deleted one can be replaced.
            models.UniqueConstraint(
                fields=['agent', 'carrier'],
                condition=models.Q(deleted_at__isnull=True),
                name='uniq_password_agent_carrier_alive',
                violation_error_message='This agent already has a password at this carrier.',
            ),
            # And one agency password at each carrier.
            models.UniqueConstraint(
                fields=['agency', 'carrier'],
                condition=models.Q(deleted_at__isnull=True, agency__isnull=False),
                name='uniq_password_agency_carrier_alive',
                violation_error_message='The agency already has a password at this carrier.',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(agent__isnull=False, agency__isnull=True)
                    | models.Q(agent__isnull=True, agency__isnull=False)
                ),
                name='password_agent_or_agency',
                violation_error_message='A password belongs to an agent or the agency.',
            ),
        ]

    def __str__(self):
        return f'{self.party} @ {self.carrier}'

    @property
    def party(self):
        """Who the login belongs to: the agent, or the agency."""
        return self.agent or self.agency

    def save(self, *args, **kwargs):
        self.username = self.username.strip()
        super().save(*args, **kwargs)
