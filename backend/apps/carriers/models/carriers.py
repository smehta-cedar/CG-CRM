from django.db import models
from django.db.models.functions import Lower

from apps.agency.models import State
from apps.base.models import BaseModel

# Every line of business a carrier can be listed under, in display order. A
# carrier's lines are stored in this order too. Stored as plain strings on the
# carrier (a JSON list), so adding one here is enough.
LINES_OF_BUSINESS = (
    'Medicare Supplement',
    'Ancillary',
    'MAPD',
    'Life',
    'Annuities',
)

# Where the agency stands with the carrier. Only "active" is in force:
# is_active (from BaseModel) follows it on every save, so ?is_active= filters
# and the summaries elsewhere keep meaning "in force".
CARRIER_STATUSES = (
    ('active', 'Active'),
    ('applied', 'Applied'),
    ('pending', 'Pending'),
    ('expired', 'Expired'),
    ('inactive', 'Inactive'),
)


class Carrier(BaseModel):
    """An insurance carrier, e.g. "Humana".

    Listed once however many lines of business it writes. Of those,
    certification_lines are the ones an appointed agent must be certified
    for. Writing numbers live on carrier contracts and portal logins on
    passwords, not here.

    `status` is one of CARRIER_STATUSES; `is_active` is derived from it
    (true only for "active") and never set on its own.
    """

    name = models.CharField(max_length=255)
    # Other names seen on statements or in conversation, e.g. ["MoO"].
    aliases = models.JSONField(default=list, blank=True)
    # At least one of LINES_OF_BUSINESS, kept in that order.
    lines_of_business = models.JSONField(default=list, blank=True)
    # Lines that need an agent certification. Always a subset of
    # lines_of_business, in the same order. Empty means none do.
    certification_lines = models.JSONField(default=list, blank=True)
    # The carrier's site or agent portal. Blank when none.
    link = models.URLField(max_length=500, blank=True)
    status = models.CharField(max_length=10, choices=CARRIER_STATUSES, default='active', db_index=True)
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
        self.is_active = self.status == 'active'
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and 'status' in update_fields:
            kwargs['update_fields'] = {*update_fields, 'is_active'}
        super().save(*args, **kwargs)
