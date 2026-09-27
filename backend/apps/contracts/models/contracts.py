from django.db import models

from apps.agency.models import State
from apps.agents.models import Agent
from apps.base.models import BaseModel
from apps.carriers.models import Carrier


class CarrierContract(BaseModel):
    """An appointment: one agent contracted with one carrier, in the states
    listed, with the writing number (producer ID) the carrier assigned them.
    Presence means contracted, absence means not: there is no status of its
    own (whether the agent is active comes from the agent).

    `appointed_states` must sit within both ceilings: the agent's licensed
    states and the carrier's available states (the API enforces it, naming
    the side that blocks a state). Empty means appointed nowhere yet, never
    "every state". The writing number is unique within a carrier when set.
    """

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='contracts')
    carrier = models.ForeignKey(Carrier, on_delete=models.CASCADE, related_name='contracts')
    writing_number = models.CharField(max_length=50, blank=True)
    appointed_states = models.ManyToManyField(State, blank=True, related_name='contracts')

    class Meta(BaseModel.Meta):
        constraints = [
            # One contract per agent at each carrier; a deleted one can be replaced.
            models.UniqueConstraint(
                fields=['agent', 'carrier'],
                condition=models.Q(deleted_at__isnull=True),
                name='uniq_contract_agent_carrier_alive',
                violation_error_message='This agent already has a contract with this carrier.',
            ),
        ]

    def __str__(self):
        return f'{self.agent} @ {self.carrier}'

    @property
    def state_codes(self):
        """Appointed state codes, in code order."""
        return sorted(state.code for state in self.appointed_states.all())

    def save(self, *args, **kwargs):
        self.writing_number = self.writing_number.strip()
        super().save(*args, **kwargs)
