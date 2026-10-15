from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Role, RolePermission, User
from apps.agency.models import Agency
from apps.agents.models import Agent
from apps.carriers.models import Carrier
from apps.passwords.models import Password
from apps.policies.models import PolicyType

from .models import AgencyCarrierContract, AgencyCarrierContractNote, CarrierContract


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
        self.advantage = PolicyType.objects.create(name='Medicare Advantage')
        self.supplement = PolicyType.objects.create(name='Medicare Supplement')
        self.sample = {
            'agency': str(self.agency.pk),
            'carrier': str(self.carrier.pk),
            'contract_number': ' HUM-001 ',
            'policy_types': [str(self.supplement.pk), str(self.advantage.pk)],
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
    def test_creates_contract_and_added_note(self):
        response = self.client.post(self.create_url(), self.sample, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data['data']
        self.assertEqual(data['contract_number'], 'HUM-001')
        self.assertEqual(
            [policy_type['name'] for policy_type in data['policy_types']],
            ['Medicare Advantage', 'Medicare Supplement'],
        )
        self.assertNotIn('password', data)
        self.assertEqual(data['status'], 'active')
        note = AgencyCarrierContractNote.objects.get(contract_id=data['id'])
        self.assertEqual(note.kind, 'added')
        self.assertEqual(
            note.changes,
            [
                {'field': 'carrier', 'from': '', 'to': 'Humana'},
                {'field': 'contract_number', 'from': '', 'to': 'HUM-001'},
                {'field': 'policy_types', 'from': '', 'to': 'Medicare Advantage, Medicare Supplement'},
                {'field': 'status', 'from': '', 'to': 'active'},
            ],
        )

    def test_blank_contract_number_and_no_policy_types_are_allowed_unless_active(self):
        body = {'agency': str(self.agency.pk), 'carrier': str(self.carrier.pk), 'contract_number': ''}
        response = self.client.post(self.create_url(), body, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['contract_number'], ['Enter the contract number for an active contract.'])
        response = self.client.post(self.create_url(), {**body, 'status': 'pending'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['data']['policy_types'], [])

    def test_one_live_contract_per_carrier(self):
        self.make_contract()
        response = self.client.post(self.create_url(), self.sample, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['carrier'], ['Humana already has an agency contract.'])

    def test_deleted_contract_can_be_replaced(self):
        self.make_contract().delete()
        self.assertEqual(self.client.post(self.create_url(), self.sample, format='json').status_code, 201)

    def test_ignores_unknown_policy_type(self):
        response = self.client.post(
            self.create_url(),
            {**self.sample, 'policy_types': [str(self.carrier.pk), str(self.advantage.pk)]},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            [policy_type['name'] for policy_type in response.data['data']['policy_types']], ['Medicare Advantage']
        )

    def test_edit_note_lists_only_changes(self):
        contract = self.make_contract(contract_number='X1')
        response = self.client.patch(
            self.detail_url(contract),
            {'contract_number': '', 'status': 'cancelled'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            contract.notes.get().changes,
            [
                {'field': 'contract_number', 'from': 'X1', 'to': ''},
                {'field': 'status', 'from': 'active', 'to': 'cancelled'},
            ],
        )

    def test_patch_replaces_policy_types_and_notes_it(self):
        contract = self.make_contract()
        contract.policy_types.set([self.advantage])
        response = self.client.patch(
            self.detail_url(contract), {'policy_types': [str(self.supplement.pk)]}, format='json'
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([t['name'] for t in response.data['data']['policy_types']], ['Medicare Supplement'])
        self.assertEqual(
            contract.notes.get().changes,
            [{'field': 'policy_types', 'from': 'Medicare Advantage', 'to': 'Medicare Supplement'}],
        )

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
    def test_only_an_active_contract_opens_the_carrier(self):
        contract = self.make_contract(contract_number='N1', status='pending')
        self.assertFalse(self.accessible()['Humana'])
        contract.status = 'active'
        contract.save()
        self.assertTrue(self.accessible()['Humana'])
        self.assertTrue(AgencyCarrierContract.objects.get(pk=contract.pk).is_active)

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
        self.staff.roles.set([make_role('agencies', can_view=True)])
        self.assertEqual(self.client.get(self.list_url()).status_code, 200)
        self.assertEqual(self.client.post(self.create_url(), self.sample, format='json').status_code, 403)


class AgencyContractAppointAgentsTests(AgencyContractAPITestCase):
    def setUp(self):
        super().setUp()
        self.ann = Agent.objects.create(name='Ann Lee', npn='111')
        self.bob = Agent.objects.create(name='Bob Ray', npn='222')

    def test_create_appoints_each_agent_pending_with_note_and_password(self):
        response = self.client.post(
            self.create_url(), {**self.sample, 'agents': [str(self.ann.pk), str(self.bob.pk)]}, format='json'
        )
        self.assertEqual(response.status_code, 201, response.data)
        contracts = CarrierContract.objects.filter(carrier=self.carrier).order_by('agent__name')
        self.assertEqual([(c.agent.name, c.status, c.writing_number) for c in contracts], [
            ('Ann Lee', 'pending', ''),
            ('Bob Ray', 'pending', ''),
        ])
        self.assertTrue(all(contract.notes.filter(kind='added').exists() for contract in contracts))
        self.assertEqual(Password.objects.filter(carrier=self.carrier, agent__isnull=False).count(), 2)

    def test_edit_skips_agents_already_appointed(self):
        contract = self.make_contract(contract_number='HUM-001')
        CarrierContract.objects.create(agent=self.ann, carrier=self.carrier, writing_number='W1', status='active')
        response = self.client.patch(
            self.detail_url(contract), {'agents': [str(self.ann.pk), str(self.bob.pk)]}, format='json'
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(CarrierContract.objects.get(agent=self.ann, carrier=self.carrier).status, 'active')
        self.assertEqual(CarrierContract.objects.get(agent=self.bob, carrier=self.carrier).status, 'pending')

    def test_agents_need_an_active_contract(self):
        response = self.client.post(
            self.create_url(), {**self.sample, 'status': 'pending', 'agents': [str(self.ann.pk)]}, format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('agents', response.data['errors'])
        self.assertFalse(AgencyCarrierContract.objects.exists())

    def test_unknown_agent_is_a_400(self):
        response = self.client.post(self.create_url(), {**self.sample, 'agents': [str(self.carrier.pk)]}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['agents'], ['Unknown agent.'])

    def test_agents_need_contracts_create_permission(self):
        staff = User.objects.create_user(email='staff@example.com', password='Sup3r-secret!', full_name='Staff')
        staff.roles.set([make_role('agencies', can_view=True, can_create=True)])
        self.client.force_authenticate(staff)
        response = self.client.post(self.create_url(), {**self.sample, 'agents': [str(self.ann.pk)]}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(CarrierContract.objects.exists())
