from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.storefront.models import Product

# The one product the shop sold while it was hard-coded (frontend/lib/shop.ts).
TEE = {
    'name': 'Cedar Grove Tee',
    'description': 'Soft ring-spun cotton with the Cedar Grove pinecone on the chest. Unisex fit, pre-shrunk.',
    # Unisex, filed under Mens so the section has something in it; change it on Storefront.
    'category': 'mens',
    'product_type': 'shirts',
    'price': Decimal('28.00'),
    'colors': [
        {'id': 'teal', 'label': 'Teal', 'hex': '#37b38f'},
        {'id': 'white', 'label': 'White', 'hex': '#ffffff'},
        {'id': 'navy', 'label': 'Navy', 'hex': '#1f2a44'},
    ],
    'sizes': ['S', 'M', 'L', 'XL', 'XXL'],
    'max_quantity': 10,
}


class Command(BaseCommand):
    """Create the Cedar Grove tee, the shop's first product.

        python manage.py seed_storefront

    Idempotent: matched by name and updated in place.
    """

    help = 'Create or update the Cedar Grove tee product.'

    def handle(self, *args, **options):
        with transaction.atomic():
            product = Product.objects.filter(name__iexact=TEE['name']).first()
            if product is None:
                Product.objects.create(**TEE)
                verb = 'created'
            else:
                for field, value in TEE.items():
                    setattr(product, field, value)
                product.save()
                verb = 'updated'
        self.stdout.write(self.style.SUCCESS(f"Product \"{TEE['name']}\" {verb}."))
