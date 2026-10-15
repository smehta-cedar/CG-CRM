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
        self.admin.phone = '(555)010-9999'
        self.admin.save(update_fields=['phone'])
        response = self.client.post(self.url('merch'), self.order, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data['data']
        self.assertEqual(data['type'], 'merch')
        self.assertEqual(data['product']['name'], 'Tee')
        # Buyer contact comes from the signed-in user, not the request body.
        self.assertEqual(data['buyer_name'], 'Admin')
        self.assertEqual(data['email'], 'admin@example.com')
        self.assertEqual(data['phone'], '(555)010-9999')
        self.assertEqual(data['address'], '')
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

    def test_shop_add_can_order_but_not_see_requests(self):
        role = Role.objects.create(name='Shop')
        RolePermission.objects.create(role=role, module='storefront.shop', can_view=True, can_create=True)
        self.shop.roles.set([role])
        response = self.client.post(self.url('merch'), {**self.order, 'quantity': 1}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.client.get(self.url('list')).status_code, 403)


class AgentOwnRequestTests(RequestAPITestCase):
    def setUp(self):
        super().setUp()
        self.agent_user = User.objects.create_user(
            email='maria@example.com', password='x', full_name='Maria Alva', agent=self.agent
        )
        other = Agent.objects.create(name='Other', npn='2')
        Request.objects.create(type='day_off', agent=other, start_date='2026-09-01', end_date='2026-09-01')
        Request.objects.create(
            type='day_off', agent=self.agent, start_date='2026-10-01', end_date='2026-10-02'
        )

    def test_calendar_shows_and_changes_only_own_requests(self):
        RolePermission.objects.create(
            role=Role.objects.get(name='Agent'), module='requests',
            can_view=True, can_create=True, can_update=True, can_delete=True,
        )
        self.client.force_authenticate(self.agent_user)
        rows = self.client.get(self.url('list')).data['data']
        self.assertEqual({row['agent']['id'] for row in rows}, {str(self.agent.pk)})
        others = Request.objects.exclude(agent=self.agent).get(type='day_off')
        self.assertEqual(self.client.get(self.url('detail', others.pk)).status_code, 404)
        self.assertEqual(self.client.delete(self.url('detail', others.pk)).status_code, 404)
        day_off = {'type': 'day_off', 'start_date': '2026-11-01', 'end_date': '2026-11-01'}
        other_agent = Agent.objects.exclude(pk=self.agent.pk).get()
        response = self.client.post(self.url('create'), {**day_off, 'agent_id': str(other_agent.pk)}, format='json')
        self.assertEqual(response.status_code, 403)
        response = self.client.post(self.url('create'), {**day_off, 'agent_id': str(self.agent.pk)}, format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def test_shop_order_lands_on_the_agents_calendar(self):
        self.agent.address_street = '1420 Cedar Grove Ln'
        self.agent.address_city = 'Austin'
        self.agent.address_state = 'TX'
        self.agent.address_zip = '78704'
        self.agent.save()
        RolePermission.objects.create(
            role=Role.objects.get(name='Agent'), module='storefront.shop', can_view=True, can_create=True
        )
        self.client.force_authenticate(self.agent_user)
        response = self.client.post(self.url('merch'), {**self.order, 'quantity': 1}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data['data']
        self.assertEqual(data['agent']['id'], str(self.agent.pk))
        self.assertEqual(data['buyer_name'], 'Maria Alva')
        self.assertEqual(data['email'], 'maria@example.com')
        self.assertEqual(data['address'], '1420 Cedar Grove Ln, Austin, TX 78704')
