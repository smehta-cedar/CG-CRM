from django.db import models

from apps.agency.models import State
from apps.agents.models import Agent
from apps.base.models import BaseModel
from apps.carriers.models import Carrier
from apps.storefront.models import Product

# licensing / contract: an agent asking for a licence or a contract in a state
# with a carrier. day_off: an agent asking for days off. merch: a visitor to
# the public shop ordering the Cedar Grove tee (no agent; the buyer's own
# details instead).
REQUEST_TYPES = (
    ('licensing', 'Licensing'),
    ('contract', 'Contract'),
    ('day_off', 'Day off'),
    ('merch', 'Merch'),
)

REQUEST_STATUSES = (
    ('pending', 'Pending'),
    ('approved', 'Approved'),
    ('denied', 'Denied'),
)


class Request(BaseModel):
    """One request for HR: an agent asking for one thing, or a tee order from
    the public shop. Every request starts pending; HR sets it approved or
    denied. Which columns are filled depends on `type` (the API checks it).
    """

    type = models.CharField(max_length=10, choices=REQUEST_TYPES)
    status = models.CharField(max_length=10, choices=REQUEST_STATUSES, default='pending')
    # Free text from whoever filed it.
    note = models.TextField(blank=True)

    # licensing, contract, day_off
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, null=True, blank=True, related_name='requests')
    # licensing, contract
    carrier = models.ForeignKey(Carrier, on_delete=models.CASCADE, null=True, blank=True, related_name='requests')
    state = models.ForeignKey(State, on_delete=models.PROTECT, null=True, blank=True, related_name='requests')
    # day_off, inclusive
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    # merch. The product may be gone from the shop later; the order keeps its link.
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    buyer_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    # Shipping address as typed, may span lines.
    address = models.TextField(blank=True)
    size = models.CharField(max_length=20, blank=True)
    # The colour's label as shown, e.g. "Teal".
    color = models.CharField(max_length=50, blank=True)
    quantity = models.PositiveIntegerField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        # Oldest first: the HR list reads top to bottom in the order things were filed.
        ordering = ('created_at',)

    def __str__(self):
        who = self.buyer_name if self.type == 'merch' else (self.agent.name if self.agent else '?')
        return f'{self.get_type_display()} - {who}'
