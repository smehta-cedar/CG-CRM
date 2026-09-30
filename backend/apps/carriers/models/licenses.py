from django.db import models

from apps.agency.models import LICENSE_STATUSES, State
from apps.base.models import BaseModel

from .carriers import Carrier

# Same statuses as the agency's licences (apps.agency.models.LICENSE_STATUSES).
CARRIER_LICENSE_STATUSES = LICENSE_STATUSES


class CarrierStateLicense(BaseModel):
    """The carrier's standing in one state, recorded like an agent's licence:
    the number, status, term and the lines (life / health) it covers there.

    Every row counts as an available state whatever its status: the carrier's
    `available_states` is kept equal to its rows' states (utils.sync_licenses),
    so appointments and policies keep reading that. The number and dates are
    blank until known.
    """

    carrier = models.ForeignKey(Carrier, on_delete=models.CASCADE, related_name='licenses')
    state = models.ForeignKey(State, on_delete=models.PROTECT, related_name='carrier_licenses')
    license_number = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=10, choices=CARRIER_LICENSE_STATUSES, default='active')
    start_date = models.DateField(null=True, blank=True)
    # The expiration date.
    end_date = models.DateField(null=True, blank=True)
    life = models.BooleanField(default=False, help_text='Covers life insurance in this state.')
    health = models.BooleanField(default=False, help_text='Covers health insurance in this state.')

    @property
    def lines_text(self):
        """"Life & Health", "Life", "Health" or "", as notes show it."""
        lines = [name for flag, name in ((self.life, 'Life'), (self.health, 'Health')) if flag]
        return ' & '.join(lines)

    class Meta(BaseModel.Meta):
        ordering = ('created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=['carrier', 'state'],
                condition=models.Q(deleted_at__isnull=True),
                name='uniq_carrier_state_license_alive',
                violation_error_message='This carrier already has this state.',
            ),
        ]

    def __str__(self):
        return f'{self.carrier} - {self.state.code}'

    def save(self, *args, **kwargs):
        self.license_number = self.license_number.strip()
        super().save(*args, **kwargs)
