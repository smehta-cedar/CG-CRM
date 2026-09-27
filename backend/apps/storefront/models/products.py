from django.db import models
from django.db.models.functions import Lower

from apps.base.models import BaseModel

# The catalog's sections and the kinds of thing in them, as the shop's nav
# lists them. A product may sit in no section (it then shows under All).
PRODUCT_CATEGORIES = (
    ('womens', 'Womens'),
    ('mens', 'Mens'),
    ('maternity', 'Maternity'),
    ('accessories', 'Accessories'),
    ('holidays', 'Holidays'),
)

PRODUCT_TYPES = (
    ('polos', 'Polos'),
    ('quarter-zips', 'Quarter Zips'),
    ('shirts', 'Shirts'),
    ('pants', 'Pants'),
    ('belts', 'Belts'),
    ('hats', 'Hats'),
    ('backpacks', 'Backpacks'),
)


class Product(BaseModel):
    """Something the public shop sells, e.g. the Cedar Grove tee.

    `colors` is a list of {"id", "label", "hex"} (the id is what an order
    picks, the hex fills the preview), `sizes` a list of size labels in
    display order. `is_active` (from BaseModel) is whether the shop lists
    it. There is no stock or payment: an order is a pending HR request the
    office confirms by hand.
    """

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    # Where the shop's nav files it; blank shows only under All.
    category = models.CharField(max_length=20, choices=PRODUCT_CATEGORIES, blank=True)
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPES, blank=True)
    # A link to a picture of it; the shop shows the drawn tee when blank.
    image_url = models.URLField(max_length=500, blank=True)
    # Whole dollars and cents.
    price = models.DecimalField(max_digits=8, decimal_places=2)
    colors = models.JSONField(default=list, blank=True)
    sizes = models.JSONField(default=list, blank=True)
    # The most one order may ask for.
    max_quantity = models.PositiveIntegerField(default=10)

    class Meta(BaseModel.Meta):
        ordering = ('priority', 'name')
        constraints = [
            # Case-insensitive, and a deleted product's name can be reused.
            models.UniqueConstraint(
                Lower('name'),
                condition=models.Q(deleted_at__isnull=True),
                name='uniq_product_name_alive',
                violation_error_message='A product with this name already exists.',
            ),
        ]

    def __str__(self):
        return self.name

    def color(self, color_id):
        """The colour dict with this id, or None."""
        return next((color for color in self.colors if color.get('id') == color_id), None)

    def save(self, *args, **kwargs):
        self.name = ' '.join(self.name.split())
        super().save(*args, **kwargs)
