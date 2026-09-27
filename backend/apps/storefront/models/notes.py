from django.db import models

from apps.base.models import BaseModel

from .products import Product


class ProductNote(BaseModel):
    """One change-log entry for a product, written by the API on every
    create and on every update that changed something. Append-only.

    `changes` is a list of {"field", "from", "to"} with display strings:
    colours by label and sizes joined with ", ", the status as
    "active" / "inactive". `created_by` (from BaseModel) is who made the change.
    """

    KIND_ADDED = 'added'
    KIND_EDITED = 'edited'
    KIND_CHOICES = (
        (KIND_ADDED, 'Added'),
        (KIND_EDITED, 'Edited'),
    )

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='notes')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    changes = models.JSONField(default=list)

    class Meta(BaseModel.Meta):
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.product} - {self.kind}'
