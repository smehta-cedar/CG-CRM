from django.db import models
from django.db.models.functions import Lower

from apps.agency.models import State
from apps.base.models import BaseModel

# Every line of business a carrier can be listed under, in display order. A
# carrier's lines are stored in this order too. Stored as plain strings on the
# carrier (a JSON list), so adding one here is enough.
LINES_OF_BUSINESS = (
    'General',
    'Supp/Ancillary',
    'MAPD',
    'Life',
    'Annuities',
)


class Carrier(BaseModel):
    """An insurance carrier, e.g. "Humana".

    Listed once however many lines of business it writes. Writing numbers
    live on carrier contracts and portal logins on passwords, not here.

    `is_active` (from BaseModel) is the carrier's status; it starts on.
    """

    name = models.CharField(max_length=255)
    # Other names seen on statements or in conversation, e.g. ["MoO"].
    aliases = models.JSONField(default=list, blank=True)
    # At least one of LINES_OF_BUSINESS, kept in that order.
    lines_of_business = models.JSONField(default=list, blank=True)
    # The carrier's footprint for the agency: one of the two ceilings on every
    # appointment with it (the other is the agent's own licences). Empty means
    # available nowhere yet, never "every state".
    available_states = models.ManyToManyField(State, blank=True, related_name='carriers')

    class Meta(BaseModel.Meta):
        constraints = [
            # Case-insensitive, and a deleted carrier's name can be reused.
            models.UniqueConstraint(
                Lower('name'),
                condition=models.Q(deleted_at__isnull=True),
                name='uniq_carrier_name_alive',
                violation_error_message='A carrier with this name already exists.',
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def state_codes(self):
        """Available state codes, in code order."""
        return sorted(state.code for state in self.available_states.all())

    def save(self, *args, **kwargs):
        self.name = ' '.join(self.name.split())
        super().save(*args, **kwargs)
