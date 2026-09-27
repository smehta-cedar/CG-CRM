import re

from django.db.models import Q
from django.shortcuts import get_object_or_404

from apps.storefront.models import Product, ProductNote

# Helpers the product views share. Checks that can reject a request live in
# apps.storefront.validators instead.

# The order a note lists changed fields in.
NOTE_FIELDS = ('name', 'description', 'category', 'product_type', 'image_url', 'price', 'colors', 'sizes', 'max_quantity', 'status')


def get_product_or_404(pk):
    return get_object_or_404(Product.objects, pk=pk)


def normalize_name(name):
    return ' '.join(name.split())


def slug(text):
    """"Forest Green" -> "forest-green": a colour's id from its label."""
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def normalize_colors(colors):
    """Trim labels, fill in a missing id from the label, lowercase the hex,
    drop blanks and keep the first of any duplicate ids in the order given."""
    seen = set()
    result = []
    for color in colors:
        label = ' '.join(color.get('label', '').split())
        color_id = (color.get('id') or slug(label)).strip().lower()
        hex_value = color.get('hex', '').strip().lower()
        if not label or not color_id or color_id in seen:
            continue
        seen.add(color_id)
        result.append({'id': color_id, 'label': label, 'hex': hex_value})
    return result


def normalize_sizes(sizes):
    """Trim each size, drop blanks and duplicates (case-insensitively), keep the order."""
    seen = set()
    result = []
    for size in sizes:
        size = ' '.join(size.split())
        key = size.lower()
        if size and key not in seen:
            seen.add(key)
            result.append(size)
    return result


def search_products(products, search):
    return products.filter(Q(name__icontains=search) | Q(description__icontains=search))


def filter_products(products, is_active=None, category=None, product_type=None):
    if is_active is not None:
        products = products.filter(is_active=is_active)
    if category:
        products = products.filter(category=category)
    if product_type:
        products = products.filter(product_type=product_type)
    return products


def save_product(product, actor, **fields):
    """Set `fields` on the product and record `actor` as updated_by."""
    for name, value in fields.items():
        setattr(product, name, value)
    product.updated_by = actor
    product.save(update_fields=[*fields, 'updated_by'])
    return product


def snapshot(product):
    """The product's fields as a note shows them."""
    return {
        'name': product.name,
        'description': product.description,
        'category': product.get_category_display() if product.category else '',
        'product_type': product.get_product_type_display() if product.product_type else '',
        'image_url': product.image_url,
        'price': f'{product.price:.2f}',
        'colors': ', '.join(color['label'] for color in product.colors),
        'sizes': ', '.join(product.sizes),
        'max_quantity': str(product.max_quantity),
        'status': 'active' if product.is_active else 'inactive',
    }


def diff_snapshots(before, after):
    """Fields whose shown value differs, in NOTE_FIELDS order.
    `before` is {} for a new product, so only its filled fields are listed."""
    changes = []
    for field in NOTE_FIELDS:
        from_value = before.get(field, '')
        to_value = after.get(field, '')
        if from_value != to_value:
            changes.append({'field': field, 'from': from_value, 'to': to_value})
    return changes


def record_note(product, actor, kind, changes):
    """Append a change note. Nothing is written when there are no changes."""
    if not changes:
        return None
    return ProductNote.objects.create(
        product=product,
        kind=kind,
        changes=changes,
        created_by=actor,
        updated_by=actor,
    )
