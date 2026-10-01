from django.db import models

from apps.base.models import BaseModel

from .carrier_policies import CarrierPolicy
from .certifications import Certification
from .policy_types import PolicyType


class PolicyTypeNote(BaseModel):
    """One change-log entry for a policy type, written by the API on every
    create and on every update that changed something. Append-only.

    `changes` is a list of {"field", "from", "to"} with display strings:
    the status as "active" / "inactive". `created_by` (from BaseModel) is who made the change.
    """

    KIND_ADDED = 'added'
    KIND_EDITED = 'edited'
    KIND_CHOICES = (
        (KIND_ADDED, 'Added'),
        (KIND_EDITED, 'Edited'),
    )

    policy_type = models.ForeignKey(PolicyType, on_delete=models.CASCADE, related_name='notes')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    changes = models.JSONField(default=list)

    class Meta(BaseModel.Meta):
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.policy_type} - {self.kind}'


class CarrierPolicyNote(BaseModel):
    """One change-log entry for a carrier policy, written by the API on every
    create and on every update that changed something. Append-only.

    `changes` is a list of {"field", "from", "to"} with display strings: the
    policy type and carrier by name, the states as comma-separated codes,
    the status as "active" / "inactive". `created_by` (from BaseModel) is
    who made the change.
    """

    KIND_ADDED = 'added'
    KIND_EDITED = 'edited'
    KIND_CHOICES = (
        (KIND_ADDED, 'Added'),
        (KIND_EDITED, 'Edited'),
    )

    policy = models.ForeignKey(CarrierPolicy, on_delete=models.CASCADE, related_name='notes')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    changes = models.JSONField(default=list)

    class Meta(BaseModel.Meta):
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.policy} - {self.kind}'


class CertificationNote(BaseModel):
    """One change-log entry for a certification, written by the API on every
    create and on every update that changed something. Append-only.

    `changes` is a list of {"field", "from", "to"} with display strings: the
    agent, policy type and carriers by name, dates as YYYY-MM-DD (blank
    when unset),
    the status as "active" / "inactive". `created_by` (from BaseModel) is
    who made the change.
    """

    KIND_ADDED = 'added'
    KIND_EDITED = 'edited'
    KIND_CHOICES = (
        (KIND_ADDED, 'Added'),
        (KIND_EDITED, 'Edited'),
    )

    certification = models.ForeignKey(Certification, on_delete=models.CASCADE, related_name='notes')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    changes = models.JSONField(default=list)

    class Meta(BaseModel.Meta):
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.certification} - {self.kind}'
