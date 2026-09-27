from django.db import models
from django.db.models.functions import Lower

from apps.base.models import BaseModel


class PolicyType(BaseModel):
    """One kind of policy the agency sells, e.g. "Medicare Advantage".

    A catalog entry on its own: carrier policies (CarrierPolicy) point at
    it, and state and county availability, agency contracts and agent
    certifications will too. It is not a carrier's line of business.

    `certification_required` is the board's "certification required" flag:
    an agent needs a certification on this type before selling it.

    `is_active` (from BaseModel) is the type's status; it starts on.
    """

    name = models.CharField(max_length=255)
    certification_required = models.BooleanField(default=False)

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

    def save(self, *args, **kwargs):
        self.name = ' '.join(self.name.split())
        super().save(*args, **kwargs)
