from django.db import models

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
    """One agent's portal login at one carrier: the portal username and
    password. Distinct from the app's own sign-in. The writing number
    (producer ID) lives on the carrier contract.

    The portal password is stored as entered so it can be shown and copied;
    access is limited to the `passwords` permission module. `is_active`
    (from BaseModel) is not used; `status` has three values.
    """

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='passwords')
    carrier = models.ForeignKey(Carrier, on_delete=models.CASCADE, related_name='passwords')
    username = models.CharField(max_length=255)
    portal_password = models.CharField(max_length=255)
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
        ]

    def __str__(self):
        return f'{self.agent} @ {self.carrier}'

    def save(self, *args, **kwargs):
        self.username = self.username.strip()
        super().save(*args, **kwargs)
