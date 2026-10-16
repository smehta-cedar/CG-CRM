from django.db import models

from apps.agency.models import Agency
from apps.base.models import BaseModel
from apps.carriers.models import Carrier
from apps.policies.models import PolicyType

# The same statuses as an agency state licence. active: in force. pending:
# waiting on the carrier. applied: the paperwork is in. expired: lapsed.
# cancelled: given up or revoked.
AGENCY_CONTRACT_STATUSES = (
    ('active', 'Active'),
    ('pending', 'Pending'),
    ('applied', 'Applied'),
    ('expired', 'Expired'),
    ('cancelled', 'Cancelled'),
)


class AgencyCarrierContract(BaseModel):
    """The agency's own contract with one carrier: the contracting number and
    the policy types (catalog entries) it covers. The agency's login at the
    carrier is an agency password (apps.passwords), not part of the contract.
    Commissions and assigning policies to agents are not modelled here.

    One live contract per carrier; a deleted one can be replaced. A carrier
    is open to agents (appointments, portal passwords) only while its live
    contract is active and has a contract number.

    `policy_types` are the kinds of policy the agency sells under this
    contract; empty means none. `status` starts active; an active contract
    must have a contract number (the API enforces it), any other status may
    leave it blank. `is_active` (from BaseModel) follows it: true only while
    active.
    """

    agency = models.ForeignKey(Agency, on_delete=models.CASCADE, related_name='carrier_contracts')
    carrier = models.ForeignKey(Carrier, on_delete=models.CASCADE, related_name='agency_contracts')
    contract_number = models.CharField(max_length=50, blank=True)
    policy_types = models.ManyToManyField(PolicyType, blank=True, related_name='agency_contracts')
    status = models.CharField(max_length=10, choices=AGENCY_CONTRACT_STATUSES, default='active')

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
        self.is_active = self.status == 'active'
        # is_active follows the status, so it is saved whenever the status is.
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and 'status' in update_fields and 'is_active' not in update_fields:
            kwargs['update_fields'] = [*update_fields, 'is_active']
        super().save(*args, **kwargs)
