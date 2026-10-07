from decimal import Decimal

from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Role, RolePermission, User

from .models import Product, ProductNote

SAMPLE = {
    'name': 'Cedar Grove Tee',
    'description': 'Soft cotton.',
    'price': '28.00',
    'colors': [{'label': 'Teal', 'hex': '#37B38F'}, {'id': 'navy', 'label': 'Navy', 'hex': '#1f2a44'}],
    'sizes': ['S', 'M', ' M ', 'L'],
}


def make_product(**overrides):
    fields = {
        'name': 'Cedar Grove Tee',
        'price': Decimal('28.00'),
        'colors': [{'id': 'teal', 'label': 'Teal', 'hex': '#37b38f'}],
        'sizes': ['S', 'M'],
        **overrides,
    }
    return Product.objects.create(**fields)


def make_role(**flags):
    role = Role.objects.create(name=f"storefront-{'-'.join(k for k, v in flags.items() if v) or 'none'}")
    RolePermission.objects.create(role=role, module='storefront', **flags)
    return role


class StorefrontAPITestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='Sup3r-secret!', full_name='Admin')
        self.client.force_authenticate(self.admin)

    def url(self, name, *args):
        return reverse(f'storefront:apis:products:{name}', args=args)


class CatalogTests(StorefrontAPITestCase):
    def test_catalog_is_public_and_lists_active_products_only(self):
        make_product()
        make_product(name='Old Hat', is_active=False)
        self.client.force_authenticate(None)
        response = self.client.get(self.url('catalog'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([p['name'] for p in response.data['data']], ['Cedar Grove Tee'])
        self.assertEqual(response.data['data'][0]['price'], Decimal('28.00'))
        self.assertEqual(response.data['data'][0]['colors'][0]['id'], 'teal')

    def test_management_list_needs_sign_in(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url('list')).status_code, 401)


class ProductCreateTests(StorefrontAPITestCase):
    def test_creates_product_normalizing_options(self):
        response = self.client.post(self.url('create'), SAMPLE, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data['data']
        # A colour without an id gets one from its label; the hex is lowercased; sizes are deduplicated.
        self.assertEqual(data['colors'], [{'id': 'teal', 'label': 'Teal', 'hex': '#37b38f'}, {'id': 'navy', 'label': 'Navy', 'hex': '#1f2a44'}])
        self.assertEqual(data['sizes'], ['S', 'M', 'L'])
        self.assertEqual(data['max_quantity'], 10)
        self.assertEqual(data['category'], '')
        note = ProductNote.objects.get(product_id=data['id'])
        self.assertEqual({c['field']: c['to'] for c in note.changes}['colors'], 'Teal, Navy')

    def test_category_type_and_image(self):
        response = self.client.post(
            self.url('create'),
            {**SAMPLE, 'category': 'mens', 'product_type': 'shirts', 'image_url': 'https://example.com/tee.jpg'},
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['data']['category'], 'mens')
        note = ProductNote.objects.get(product_id=response.data['data']['id'])
        self.assertEqual({c['field']: c['to'] for c in note.changes}['product_type'], 'Shirts')
        response = self.client.post(self.url('create'), {**SAMPLE, 'name': 'Other', 'category': 'kids'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('category', response.data['errors'])
        response = self.client.get(self.url('list'), {'category': 'mens'})
        self.assertEqual([p['name'] for p in response.data['data']], ['Cedar Grove Tee'])

    def test_needs_a_colour_and_a_size(self):
        response = self.client.post(self.url('create'), {**SAMPLE, 'colors': []}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('colors', response.data['errors'])
        response = self.client.post(self.url('create'), {**SAMPLE, 'sizes': ['', ' ']}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('sizes', response.data['errors'])

    def test_rejects_bad_hex_and_duplicate_name(self):
        response = self.client.post(self.url('create'), {**SAMPLE, 'colors': [{'label': 'X', 'hex': 'red'}]}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('colors', response.data['errors'])
        make_product()
        response = self.client.post(self.url('create'), {**SAMPLE, 'name': 'cedar grove tee'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('name', response.data['errors'])


class ProductDetailTests(StorefrontAPITestCase):
    def test_patch_records_note_and_delete_hides_from_catalog(self):
        product = make_product()
        response = self.client.patch(self.url('detail', product.pk), {'price': '30.00', 'is_active': False}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            product.notes.get().changes,
            [{'field': 'price', 'from': '28.00', 'to': '30.00'}, {'field': 'status', 'from': 'active', 'to': 'inactive'}],
        )
        self.assertEqual(self.client.delete(self.url('detail', product.pk)).status_code, 200)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url('catalog')).data['data'], [])

    def test_patch_cannot_remove_every_size(self):
        product = make_product()
        response = self.client.patch(self.url('detail', product.pk), {'sizes': []}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('sizes', response.data['errors'])


class StorefrontPermissionTests(StorefrontAPITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(email='staff@example.com', password='Sup3r-secret!', full_name='Staff')
        self.client.force_authenticate(self.staff)

    def test_no_role_gets_403(self):
        self.assertEqual(self.client.get(self.url('list')).status_code, 403)

    def test_view_only_role_can_list_but_not_create(self):
        # The user's permissions are cached per instance, so the role goes on before the first request.
        self.staff.roles.set([make_role(can_view=True)])
        self.assertEqual(self.client.get(self.url('list')).status_code, 200)
        self.assertEqual(self.client.post(self.url('create'), SAMPLE, format='json').status_code, 403)
