from django.db import models
from django.db.models.functions import Lower

from apps.agency.models import State
from apps.base.models import BaseModel
from apps.carriers.models import Carrier

from .policy_types import PolicyType


class CarrierPolicy(BaseModel):
    """One named policy a carrier offers, e.g. Humana's "Gold Plus HMO".

    It points at one policy type from the catalog. Agency contracts,
    commissions, agent certifications and counties are not modelled here.

    `available_states` is where the policy can be sold: always within the
    carrier's own available_states. Empty means nowhere, never "every state".

    `is_active` (from BaseModel) is the policy's status; it starts on.
    """

    carrier = models.ForeignKey(Carrier, on_delete=models.CASCADE, related_name='policies')
    policy_type = models.ForeignKey(PolicyType, on_delete=models.PROTECT, related_name='carrier_policies')
    name = models.CharField(max_length=255)
    available_states = models.ManyToManyField(State, blank=True, related_name='carrier_policies')

    class Meta(BaseModel.Meta):
        verbose_name_plural = 'carrier policies'
        constraints = [
            # Unique per carrier, ignoring case; a deleted policy's name can be
            # reused, and two carriers may use the same name.
            models.UniqueConstraint(
                'carrier',
                Lower('name'),
                condition=models.Q(deleted_at__isnull=True),
                name='uniq_carrier_policy_name_alive',
                violation_error_message='This carrier already has a policy with this name.',
            ),
        ]

    def __str__(self):
        return f'{self.carrier} - {self.name}'

    @property
    def state_codes(self):
        """Available state codes, in code order."""
        return sorted(state.code for state in self.available_states.all())

    def save(self, *args, **kwargs):
        self.name = ' '.join(self.name.split())
        super().save(*args, **kwargs)
