from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Role, RolePermission, User
from apps.agents.models import Agent
from apps.carriers.models import Carrier
from apps.storefront.models import Product

from .models import Request


def make_role(**flags):
    role = Role.objects.create(name=f"requests-{'-'.join(k for k, v in flags.items() if v) or 'none'}")
    RolePermission.objects.create(role=role, module='requests', **flags)
    return role


class RequestAPITestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='Sup3r-secret!', full_name='Admin')
        self.client.force_authenticate(self.admin)
        self.agent = Agent.objects.create(name='Maria Alva', npn='1')
        self.carrier = Carrier.objects.create(name='Humana', lines_of_business=['MAPD'])
        self.product = Product.objects.create(
            name='Tee', price='28.00', colors=[{'id': 'teal', 'label': 'Teal', 'hex': '#37b38f'}], sizes=['M'], max_quantity=2
        )
        self.order = {
            'product_id': str(self.product.pk),
            'buyer_name': 'Shop  Check',
            'email': 'Buyer@Example.com',
            'phone': '(555)010-9999',
            'address': '1 Main St',
            'size': 'M',
            'color': 'teal',
            'quantity': 2,
        }

    def url(self, name, *args):
        return reverse(f'requests:apis:requests:{name}', args=args)


class RequestCreateTests(RequestAPITestCase):
    def test_files_a_licensing_request(self):
        response = self.client.post(
            self.url('create'),
            {'type': 'licensing', 'agent_id': str(self.agent.pk), 'carrier_id': str(self.carrier.pk), 'state': 'tx', 'note': ' Two referrals. '},
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data['data']
        self.assertEqual(data['status'], 'pending')
        self.assertEqual(data['state'], 'TX')
        self.assertEqual(data['carrier']['name'], 'Humana')
        self.assertEqual(data['note'], 'Two referrals.')
        self.assertEqual(data['created_by'], 'Admin')

    def test_licensing_needs_state_and_carrier(self):
        response = self.client.post(self.url('create'), {'type': 'contract', 'agent_id': str(self.agent.pk)}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('state', response.data['errors'])
        response = self.client.post(
            self.url('create'), {'type': 'contract', 'agent_id': str(self.agent.pk), 'state': 'TX'}, format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('carrier_id', response.data['errors'])

    def test_day_off_needs_ordered_dates(self):
        body = {'type': 'day_off', 'agent_id': str(self.agent.pk), 'start_date': '2026-10-02', 'end_date': '2026-09-28'}
        response = self.client.post(self.url('create'), body, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('end_date', response.data['errors'])
        response = self.client.post(self.url('create'), {**body, 'end_date': '2026-10-02'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNone(response.data['data']['carrier'])

    def test_merch_order(self):
        response = self.client.post(self.url('merch'), self.order, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data['data']
        self.assertEqual(data['type'], 'merch')
        self.assertEqual(data['product']['name'], 'Tee')
        self.assertEqual(data['buyer_name'], 'Shop Check')
        self.assertEqual(data['email'], 'buyer@example.com')
        # The colour is stored by its label.
        self.assertEqual(data['color'], 'Teal')
        self.assertEqual(data['quantity'], 2)
        self.assertIsNone(data['agent'])

    def test_merch_is_checked_against_the_product(self):
        for bad, field in (({'quantity': 3}, 'quantity'), ({'size': 'XL'}, 'size'), ({'color': 'red'}, 'color')):
            response = self.client.post(self.url('merch'), {**self.order, **bad}, format='json')
            self.assertEqual(response.status_code, 400, bad)
            self.assertIn(field, response.data['errors'])

    def test_merch_needs_an_active_product(self):
        self.product.is_active = False
        self.product.save()
        response = self.client.post(self.url('merch'), self.order, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('product_id', response.data['errors'])


class RequestListAndDetailTests(RequestAPITestCase):
    def test_lists_oldest_first_and_filters(self):
        first = Request.objects.create(type='day_off', agent=self.agent, start_date='2026-09-01', end_date='2026-09-02')
        Request.objects.create(type='merch', buyer_name='B', status='approved')
        response = self.client.get(self.url('list'))
        self.assertEqual([r['type'] for r in response.data['data']], ['day_off', 'merch'])
        response = self.client.get(self.url('list'), {'status': 'pending'})
        self.assertEqual([r['id'] for r in response.data['data']], [str(first.pk)])

    def test_patch_status(self):
        filed = Request.objects.create(type='day_off', agent=self.agent, start_date='2026-09-01', end_date='2026-09-02')
        response = self.client.patch(self.url('detail', filed.pk), {'status': 'approved'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['status'], 'approved')
        response = self.client.patch(self.url('detail', filed.pk), {'status': 'later'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_delete_is_soft(self):
        filed = Request.objects.create(type='merch', buyer_name='B')
        self.assertEqual(self.client.delete(self.url('detail', filed.pk)).status_code, 200)
        self.assertFalse(Request.objects.filter(pk=filed.pk).exists())
        self.assertTrue(Request.all_objects.filter(pk=filed.pk).exists())


class RequestPermissionTests(RequestAPITestCase):
    def setUp(self):
        super().setUp()
        self.shop = User.objects.create_user(email='shop@example.com', password='Sup3r-secret!', full_name='Shop')
        self.client.force_authenticate(self.shop)

    def test_no_role_gets_403(self):
        self.assertEqual(self.client.get(self.url('list')).status_code, 403)

    def test_create_role_can_file_but_not_decide(self):
        self.shop.roles.set([make_role(can_view=True, can_create=True)])
        response = self.client.post(self.url('merch'), {**self.order, 'quantity': 1}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(
            self.client.patch(self.url('detail', response.data['data']['id']), {'status': 'approved'}, format='json').status_code,
            403,
        )
