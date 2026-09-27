from django.db import models

from apps.agency.models import Agency
from apps.base.models import BaseModel
from apps.carriers.models import Carrier
from apps.policies.models import CarrierPolicy


class AgencyCarrierContract(BaseModel):
    """The agency's own contract with one carrier: the contracting number,
    the carrier policies it covers and the agency's login at that carrier.
    Commissions and assigning policies to agents are not modelled here.

    One live contract per carrier; a deleted one can be replaced. A carrier
    is open to agents (appointments, portal passwords) only once its live
    contract has a contract number: blank means "not yet".

    `policies` must all belong to `carrier` (the API enforces it); empty
    means none. `username` and `password` are both blank or both set; the
    password is stored as entered so it can be shown and copied, and never
    written into a note. `is_active` (from BaseModel) is the contract's
    status; it starts on.
    """

    agency = models.ForeignKey(Agency, on_delete=models.CASCADE, related_name='carrier_contracts')
    carrier = models.ForeignKey(Carrier, on_delete=models.CASCADE, related_name='agency_contracts')
    contract_number = models.CharField(max_length=50, blank=True)
    policies = models.ManyToManyField(CarrierPolicy, blank=True, related_name='agency_contracts')
    username = models.CharField(max_length=255, blank=True)
    password = models.CharField(max_length=255, blank=True)

    class Meta(BaseModel.Meta):
        constraints = [
            # One live contract per carrier; a deleted one can be replaced.
            models.UniqueConstraint(
                fields=['carrier'],
                condition=models.Q(deleted_at__isnull=True),
                name='uniq_agency_contract_carrier_alive',
                violation_error_message='This carrier already has an agency contract.',
            ),
        ]

    def __str__(self):
        return f'{self.agency} @ {self.carrier}'

    @property
    def policy_names(self):
        """Covered policy names, in name order."""
        return sorted((policy.name for policy in self.policies.all()), key=str.lower)

    def save(self, *args, **kwargs):
        self.contract_number = self.contract_number.strip()
        self.username = self.username.strip()
        super().save(*args, **kwargs)
