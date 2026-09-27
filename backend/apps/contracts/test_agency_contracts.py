from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Role, RolePermission, User
from apps.agency.models import Agency
from apps.carriers.models import Carrier
from apps.policies.models import CarrierPolicy, PolicyType

from .models import AgencyCarrierContract, AgencyCarrierContractNote


def make_role(module, **flags):
    role = Role.objects.create(name=f"{module}-{'-'.join(k for k, v in flags.items() if v) or 'none'}")
    RolePermission.objects.create(role=role, module=module, **flags)
    return role


class AgencyContractAPITestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='Sup3r-secret!', full_name='Admin')
        self.client.force_authenticate(self.admin)
        self.agency = Agency.objects.create(name='Cedar Grove')
        self.carrier = Carrier.objects.create(name='Humana', lines_of_business=['MAPD'])
        self.other_carrier = Carrier.objects.create(name='Aetna', lines_of_business=['MAPD'])
        policy_type = PolicyType.objects.create(name='Medicare Advantage')
        self.gold = CarrierPolicy.objects.create(carrier=self.carrier, policy_type=policy_type, name='Gold Plus HMO')
        self.basic = CarrierPolicy.objects.create(carrier=self.carrier, policy_type=policy_type, name='Basic PPO')
        self.foreign = CarrierPolicy.objects.create(carrier=self.other_carrier, policy_type=policy_type, name='Aetna Value')
        self.sample = {
            'agency': str(self.agency.pk),
            'carrier': str(self.carrier.pk),
            'contract_number': ' HUM-001 ',
            'policies': [str(self.gold.pk), str(self.basic.pk)],
            'username': 'cedar.grove',
            'password': 'top secret',
        }

    def make_contract(self, carrier=None, contract_number='', **fields):
        return AgencyCarrierContract.objects.create(
            agency=self.agency, carrier=carrier or self.carrier, contract_number=contract_number, **fields
        )

    def list_url(self):
        return reverse('contracts:apis:agency_contracts:list')

    def create_url(self):
        return reverse('contracts:apis:agency_contracts:create')

    def detail_url(self, contract):
        return reverse('contracts:apis:agency_contracts:detail', args=[contract.pk])

    def notes_url(self, contract):
        return reverse('contracts:apis:agency_contracts:notes', args=[contract.pk])


class AgencyContractCreateTests(AgencyContractAPITestCase):
    def test_creates_contract_and_added_note_without_password(self):
        response = self.client.post(self.create_url(), self.sample, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data['data']
        self.assertEqual(data['contract_number'], 'HUM-001')
        self.assertEqual([policy['name'] for policy in data['policies']], ['Basic PPO', 'Gold Plus HMO'])
        self.assertEqual(data['password'], 'top secret')
        self.assertTrue(data['is_active'])
        note = AgencyCarrierContractNote.objects.get(contract_id=data['id'])
        self.assertEqual(note.kind, 'added')
        self.assertEqual(
            note.changes,
            [
                {'field': 'carrier', 'from': '', 'to': 'Humana'},
                {'field': 'contract_number', 'from': '', 'to': 'HUM-001'},
                {'field': 'policies', 'from': '', 'to': 'Basic PPO, Gold Plus HMO'},
                {'field': 'username', 'from': '', 'to': 'cedar.grove'},
                {'field': 'status', 'from': '', 'to': 'active'},
            ],
        )
        self.assertNotIn('top secret', str(note.changes))

    def test_blank_contract_number_and_no_policies_or_login_are_allowed(self):
        response = self.client.post(
            self.create_url(),
            {'agency': str(self.agency.pk), 'carrier': str(self.carrier.pk), 'contract_number': ''},
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['data']['policies'], [])

    def test_one_live_contract_per_carrier(self):
        self.make_contract()
        response = self.client.post(self.create_url(), self.sample, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['carrier'], ['Humana already has an agency contract.'])

    def test_deleted_contract_can_be_replaced(self):
        self.make_contract().delete()
        self.assertEqual(self.client.post(self.create_url(), self.sample, format='json').status_code, 201)

    def test_rejects_another_carriers_policy(self):
        response = self.client.post(
            self.create_url(), {**self.sample, 'policies': [str(self.foreign.pk)]}, format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['policies'], ['Aetna Value is not a Humana policy.'])

    def test_login_is_both_or_neither(self):
        response = self.client.post(self.create_url(), {**self.sample, 'password': '  '}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('password', response.data['errors'])
        response = self.client.post(self.create_url(), {**self.sample, 'username': ''}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('username', response.data['errors'])


class AgencyContractDetailTests(AgencyContractAPITestCase):
    def test_edit_note_lists_only_changes_and_never_the_password(self):
        contract = self.make_contract(contract_number='X1', username='a', password='old')
        response = self.client.patch(
            self.detail_url(contract),
            {'contract_number': '', 'password': 'new-secret', 'is_active': False},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            contract.notes.get().changes,
            [
                {'field': 'contract_number', 'from': 'X1', 'to': ''},
                {'field': 'status', 'from': 'active', 'to': 'inactive'},
            ],
        )

    def test_password_only_change_writes_no_note(self):
        contract = self.make_contract(username='a', password='old')
        response = self.client.patch(self.detail_url(contract), {'password': 'new'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(contract.notes.exists())

    def test_changing_carrier_rechecks_kept_policies(self):
        contract = self.make_contract()
        contract.policies.set([self.gold])
        response = self.client.patch(self.detail_url(contract), {'carrier': str(self.other_carrier.pk)}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('policies', response.data['errors'])

    def test_list_sorted_by_carrier_and_filtered(self):
        self.make_contract()
        self.make_contract(carrier=self.other_carrier)
        response = self.client.get(self.list_url())
        self.assertEqual([row['carrier']['name'] for row in response.data['data']], ['Aetna', 'Humana'])
        response = self.client.get(self.list_url(), {'carrier': str(self.carrier.pk)})
        self.assertEqual([row['carrier']['name'] for row in response.data['data']], ['Humana'])

    def test_delete_and_notes_endpoint(self):
        contract = self.make_contract()
        self.client.patch(self.detail_url(contract), {'contract_number': 'N1'}, format='json')
        self.assertEqual(len(self.client.get(self.notes_url(contract)).data['data']), 1)
        self.assertEqual(self.client.delete(self.detail_url(contract)).status_code, 200)
        self.assertEqual(self.client.get(self.list_url()).data['data'], [])


class CarrierAgentAccessTests(AgencyContractAPITestCase):
    def accessible(self):
        response = self.client.get(reverse('carriers:apis:carriers:list'))
        return {row['name']: row['agent_accessible'] for row in response.data['data']}

    def test_flag_needs_a_live_contract_with_a_number(self):
        self.assertEqual(self.accessible(), {'Aetna': False, 'Humana': False})
        contract = self.make_contract()
        self.assertEqual(self.accessible()['Humana'], False)
        contract.contract_number = 'N1'
        contract.save()
        self.assertEqual(self.accessible(), {'Aetna': False, 'Humana': True})
        contract.delete()
        self.assertEqual(self.accessible()['Humana'], False)


class AgencyContractPermissionTests(AgencyContractAPITestCase):
    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_user(email='staff@example.com', password='Sup3r-secret!', full_name='Staff')
        self.client.force_authenticate(self.staff)

    def test_no_role_gets_403(self):
        self.assertEqual(self.client.get(self.list_url()).status_code, 403)

    def test_view_only_role_can_list_but_not_create(self):
        self.staff.role = make_role('agency_contracts', can_view=True)
        self.staff.save()
        self.assertEqual(self.client.get(self.list_url()).status_code, 200)
        self.assertEqual(self.client.post(self.create_url(), self.sample, format='json').status_code, 403)
