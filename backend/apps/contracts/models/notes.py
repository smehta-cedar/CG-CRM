from django.db import models

from apps.base.models import BaseModel

from .agency_contracts import AgencyCarrierContract
from .contracts import CarrierContract


class CarrierContractNote(BaseModel):
    """One change-log entry for a contract, written by the API on every
    create and on every update that changed something. Append-only.

    `changes` is a list of {"field", "from", "to"} with display strings: the
    agent and carrier by name, states as codes joined with ", ". `created_by`
    (from BaseModel) is who made the change.
    """

    KIND_ADDED = 'added'
    KIND_EDITED = 'edited'
    KIND_CHOICES = (
        (KIND_ADDED, 'Added'),
        (KIND_EDITED, 'Edited'),
    )

    contract = models.ForeignKey(CarrierContract, on_delete=models.CASCADE, related_name='notes')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    changes = models.JSONField(default=list)

    class Meta(BaseModel.Meta):
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.contract} - {self.kind}'


class AgencyCarrierContractNote(BaseModel):
    """One change-log entry for an agency contract, written by the API on
    every create and on every update that changed something. Append-only.

    `changes` is a list of {"field", "from", "to"} with display strings: the
    carrier by name, policies as names joined with ", ", the status as
    "active" / "inactive". The password is never recorded. `created_by`
    (from BaseModel) is who made the change.
    """

    KIND_ADDED = 'added'
    KIND_EDITED = 'edited'
    KIND_CHOICES = (
        (KIND_ADDED, 'Added'),
        (KIND_EDITED, 'Edited'),
    )

    contract = models.ForeignKey(AgencyCarrierContract, on_delete=models.CASCADE, related_name='notes')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    changes = models.JSONField(default=list)

    class Meta(BaseModel.Meta):
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.contract} - {self.kind}'
