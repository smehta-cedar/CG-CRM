from django.db import models

from apps.agents.models import Agent
from apps.base.models import BaseModel

from .policy_types import PolicyType


class Certification(BaseModel):
    """One agent certified for one policy type, e.g. Maria Alva on
    "Medicare Advantage".

    The same rows are added from the agent's profile and from the policy
    type's row. Carrier-policy certificates, agency contracts, commissions
    and any rule that blocks a sale are not modelled here.

    `start_date` and `end_date` are optional; when both are set the end is
    on or after the start (the API enforces that). `is_active` (from
    BaseModel) is the certification's status; it starts on.
    """

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='certifications')
    policy_type = models.ForeignKey(PolicyType, on_delete=models.PROTECT, related_name='certifications')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        constraints = [
            # One live row per agent and policy type; a deleted pair can be added again.
            models.UniqueConstraint(
                fields=['agent', 'policy_type'],
                condition=models.Q(deleted_at__isnull=True),
                name='uniq_certification_pair_alive',
                violation_error_message='This agent is already certified for this policy type.',
            ),
        ]

    def __str__(self):
        return f'{self.agent} - {self.policy_type}'
