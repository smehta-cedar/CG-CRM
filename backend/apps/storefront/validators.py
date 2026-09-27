from rest_framework.exceptions import ValidationError

from apps.storefront.models import Product

# Every check the product views run. Each one returns nothing when the check
# passes and raises ValidationError (400, field errors under "errors").


def ensure_name_free(name, exclude=None):
    products = Product.objects.filter(name__iexact=name)
    if exclude is not None:
        products = products.exclude(pk=exclude.pk)
    if products.exists():
        raise ValidationError({'name': ['A product with this name already exists.']})


def ensure_options(colors, sizes):
    """A product needs at least one colour and one size to be ordered."""
    if not colors:
        raise ValidationError({'colors': ['Add at least one colour.']})
    if not sizes:
        raise ValidationError({'sizes': ['Add at least one size.']})


def ensure_order_fits(product, color_id, size, quantity):
    """An order's colour, size and quantity must be ones the product offers.
    Returns the colour dict, so the order can store its label."""
    color = product.color(color_id)
    if color is None:
        raise ValidationError({'color': ['Choose a colour.']})
    if size not in product.sizes:
        raise ValidationError({'size': ['Choose a size.']})
    if quantity < 1 or quantity > product.max_quantity:
        raise ValidationError({'quantity': [f'Enter a quantity from 1 to {product.max_quantity}.']})
    return color
