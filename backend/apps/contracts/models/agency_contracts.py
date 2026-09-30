from django.db import models

from apps.agency.models import Agency
from apps.base.models import BaseModel
from apps.carriers.models import Carrier
from apps.policies.models import PolicyType


class AgencyCarrierContract(BaseModel):
    """The agency's own contract with one carrier: the contracting number and
    the policy types (catalog entries) it covers. The agency's login at the
    carrier is an agency password (apps.passwords), not part of the contract.
    Commissions and assigning policies to agents are not modelled here.

    One live contract per carrier; a deleted one can be replaced. A carrier
    is open to agents (appointments, portal passwords) only once its live
    contract has a contract number: blank means "not yet".

    `policy_types` are the kinds of policy the agency sells under this
    contract; empty means none. `is_active` (from BaseModel) is the
    contract's status; it starts on.
    """

    agency = models.ForeignKey(Agency, on_delete=models.CASCADE, related_name='carrier_contracts')
    carrier = models.ForeignKey(Carrier, on_delete=models.CASCADE, related_name='agency_contracts')
    contract_number = models.CharField(max_length=50, blank=True)
    policy_types = models.ManyToManyField(PolicyType, blank=True, related_name='agency_contracts')

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
    def policy_type_names(self):
        """Covered policy type names, in name order."""
        return sorted((policy_type.name for policy_type in self.policy_types.all()), key=str.lower)

    def save(self, *args, **kwargs):
        self.contract_number = self.contract_number.strip()
        super().save(*args, **kwargs)
