from django.db import models
from django.db.models.functions import Lower

from apps.base.models import BaseModel
from apps.carriers.models import Carrier


class PolicyType(BaseModel):
    """One kind of policy the agency sells, e.g. "Medicare Advantage".

    A catalog entry on its own: carrier policies (CarrierPolicy) point at
    it, and state and county availability, agency contracts and agent
    certifications will too. It is not a carrier's line of business.

    `certification_scope` is how an agent gets certified on this type:
    "none" (no certification needed), "single" (one certification covers
    the type) or "per_carrier" (certified against the carriers in
    `certification_carriers`). Nothing here blocks a sale; it is recorded
    for the catalog only.

    `certification_carriers` is only filled when the scope is per_carrier,
    and then holds at least one carrier; each must have a live agency
    contract when it is saved (the API enforces all of this). A carrier
    left out does not need this certification for this type.

    `is_active` (from BaseModel) is the type's status; it starts on.
    """

    SCOPE_NONE = 'none'
    SCOPE_SINGLE = 'single'
    SCOPE_PER_CARRIER = 'per_carrier'
    SCOPE_CHOICES = (
        (SCOPE_NONE, 'None'),
        (SCOPE_SINGLE, 'Single'),
        (SCOPE_PER_CARRIER, 'Per carrier'),
    )

    name = models.CharField(max_length=255)
    certification_scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default=SCOPE_NONE)
    certification_carriers = models.ManyToManyField(
        Carrier, blank=True, related_name='certification_policy_types'
    )

    class Meta(BaseModel.Meta):
        constraints = [
            # Case-insensitive, and a deleted type's name can be reused.
            models.UniqueConstraint(
                Lower('name'),
                condition=models.Q(deleted_at__isnull=True),
                name='uniq_policy_type_name_alive',
                violation_error_message='A policy type with this name already exists.',
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def certification_carrier_names(self):
        """Carriers that need this certification, in name order."""
        return sorted((carrier.name for carrier in self.certification_carriers.all()), key=str.lower)

    def save(self, *args, **kwargs):
        self.name = ' '.join(self.name.split())
        super().save(*args, **kwargs)
