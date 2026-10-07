from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Role, RolePermission, User
from apps.agency.models import Agency, State
from apps.agents.models import Agent, AgentStateLicense
from apps.carriers.models import Carrier

from .models import AgencyCarrierContract, CarrierContract, CarrierContractNote


def make_role(**flags):
    role = Role.objects.create(name=f"contracts-{'-'.join(k for k, v in flags.items() if v) or 'none'}")
    RolePermission.objects.create(role=role, module='contracts', **flags)
    return role


class ContractAPITestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='Sup3r-secret!', full_name='Admin')
        self.client.force_authenticate(self.admin)
        # Maria is licensed in FL, LA, TX; Humana is available in FL, TX; so the ceiling is FL, TX.
        self.agent = Agent.objects.create(name='Maria Alva', npn='1')
        for code in ('FL', 'LA', 'TX'):
            AgentStateLicense.objects.create(agent=self.agent, state=State.objects.get(code=code), license_number='n')
        self.other_agent = Agent.objects.create(name='James Carter', npn='2')
        self.carrier = Carrier.objects.create(name='Humana', lines_of_business=['MAPD'])
        self.carrier.available_states.set(State.objects.filter(code__in=['FL', 'TX']))
        self.other_carrier = Carrier.objects.create(name='UHC', lines_of_business=['MAPD'])
        # Agents can only be given a carrier whose agency contract has a number.
        self.agency = Agency.objects.create(name='Cedar Grove')
        for carrier, number in ((self.carrier, 'A-1'), (self.other_carrier, 'A-2')):
            AgencyCarrierContract.objects.create(agency=self.agency, carrier=carrier, contract_number=number)
        self.sample = {
            'agent_id': str(self.agent.pk),
            'carrier_id': str(self.carrier.pk),
            'writing_number': 'H4471902',
            'appointed_states': ['TX', 'FL'],
        }

    def make_contract(self, agent=None, carrier=None, writing_number='', states=()):
        contract = CarrierContract.objects.create(
            agent=agent or self.agent, carrier=carrier or self.carrier, writing_number=writing_number
        )
        contract.appointed_states.set(State.objects.filter(code__in=states))
        return contract

    def list_url(self):
        return reverse('contracts:apis:contracts:list')

    def create_url(self):
        return reverse('contracts:apis:contracts:create')

    def detail_url(self, contract):
        return reverse('contracts:apis:contracts:detail', args=[contract.pk])

    def notes_url(self, contract):
        return reverse('contracts:apis:contracts:notes', args=[contract.pk])

    def notes_all_url(self):
        return reverse('contracts:apis:contracts:notes-all')


class ContractCreateTests(ContractAPITestCase):
    def test_creates_contract_within_ceiling(self):
        response = self.client.post(self.create_url(), self.sample, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data['data']
        self.assertEqual(data['agent']['name'], 'Maria Alva')
        self.assertEqual(data['carrier']['name'], 'Humana')
        self.assertEqual(data['appointed_states'], ['FL', 'TX'])
        note = CarrierContractNote.objects.get(contract_id=data['id'])
        self.assertEqual(
            note.changes,
            [
                {'field': 'agent', 'from': '', 'to': 'Maria Alva'},
                {'field': 'carrier', 'from': '', 'to': 'Humana'},
                {'field': 'writing_number', 'from': '', 'to': 'H4471902'},
                {'field': 'appointed_states', 'from': '', 'to': 'FL, TX'},
            ],
        )

    def test_rejects_state_the_carrier_lacks_naming_the_carrier(self):
        response = self.client.post(self.create_url(), {**self.sample, 'appointed_states': ['LA']}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Humana isn't available in LA", response.data['errors']['appointed_states'][0])

    def test_rejects_state_the_agent_lacks_naming_the_agent(self):
        self.carrier.available_states.add(State.objects.get(code='GA'))
        response = self.client.post(self.create_url(), {**self.sample, 'appointed_states': ['GA']}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Maria Alva isn't licensed in GA", response.data['errors']['appointed_states'][0])

    def test_rejects_second_contract_for_same_pair(self):
        self.make_contract()
        response = self.client.post(self.create_url(), self.sample, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['agent_id'], ['Maria Alva already has a contract with Humana.'])

    def test_rejects_writing_number_used_at_carrier_ignoring_case(self):
        self.make_contract(agent=self.other_agent, writing_number='h4471902')
        response = self.client.post(self.create_url(), {**self.sample, 'appointed_states': []}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('James Carter', response.data['errors']['writing_number'][0])

    def test_same_writing_number_at_another_carrier_is_fine(self):
        self.make_contract(agent=self.other_agent, carrier=self.other_carrier, writing_number='H4471902')
        response = self.client.post(self.create_url(), {**self.sample, 'appointed_states': []}, format='json')
        self.assertEqual(response.status_code, 201, response.data)


class ContractCarrierAccessTests(ContractAPITestCase):
    MESSAGE = ['Add a contract number before an agent can use this carrier.']

    def test_rejects_carrier_whose_agency_contract_has_no_number(self):
        AgencyCarrierContract.objects.filter(carrier=self.carrier).update(contract_number='')
        response = self.client.post(self.create_url(), self.sample, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['carrier'], self.MESSAGE)

    def test_rejects_carrier_without_agency_contract(self):
        AgencyCarrierContract.objects.filter(carrier=self.carrier).delete()
        response = self.client.post(self.create_url(), self.sample, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['carrier'], self.MESSAGE)

    def test_edit_keeping_an_inaccessible_carrier_is_allowed(self):
        contract = self.make_contract(states=['TX'])
        AgencyCarrierContract.objects.filter(carrier=self.carrier).update(contract_number='')
        response = self.client.patch(
            self.detail_url(contract),
            {'carrier_id': str(self.carrier.pk), 'writing_number': 'W1'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)

    def test_edit_moving_to_an_inaccessible_carrier_is_rejected(self):
        contract = self.make_contract()
        AgencyCarrierContract.objects.filter(carrier=self.other_carrier).update(contract_number='')
        response = self.client.patch(self.detail_url(contract), {'carrier_id': str(self.other_carrier.pk)}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['carrier'], self.MESSAGE)


class ContractListTests(ContractAPITestCase):
    def test_lists_by_agent_then_carrier_and_filters_by_state(self):
        self.make_contract(agent=self.other_agent, carrier=self.other_carrier)
        self.make_contract(states=['TX'])
        response = self.client.get(self.list_url())
        self.assertEqual(
            [(c['agent']['name'], c['carrier']['name']) for c in response.data['data']],
            [('James Carter', 'UHC'), ('Maria Alva', 'Humana')],
        )
        response = self.client.get(self.list_url(), {'state': 'tx'})
        self.assertEqual([c['agent']['name'] for c in response.data['data']], ['Maria Alva'])


class ContractDetailTests(ContractAPITestCase):
    def test_patch_states_records_note(self):
        contract = self.make_contract(states=['FL', 'TX'])
        response = self.client.patch(self.detail_url(contract), {'appointed_states': ['TX']}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['appointed_states'], ['TX'])
        self.assertEqual(contract.notes.get().changes, [{'field': 'appointed_states', 'from': 'FL, TX', 'to': 'TX'}])

    def test_patch_rechecks_ceiling_when_carrier_changes(self):
        contract = self.make_contract(states=['TX'])
        response = self.client.patch(self.detail_url(contract), {'carrier_id': str(self.other_carrier.pk)}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("UHC isn't available in TX", response.data['errors']['appointed_states'][0])

    def test_patch_without_change_writes_no_note(self):
        contract = self.make_contract(writing_number='X1')
        response = self.client.patch(self.detail_url(contract), {'writing_number': 'X1'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(contract.notes.exists())

    def test_delete_frees_the_pair_and_notes_endpoints(self):
        contract = self.make_contract()
        self.client.patch(self.detail_url(contract), {'writing_number': 'W9'}, format='json')
        self.assertEqual(len(self.client.get(self.notes_url(contract)).data['data']), 1)
        self.assertEqual(self.client.get(self.notes_all_url()).data['meta']['total_items'], 1)
        self.assertEqual(self.client.delete(self.detail_url(contract)).status_code, 200)
        self.assertEqual(self.client.post(self.create_url(), {**self.sample, 'appointed_states': []}, format='json').status_code, 201)
        # A deleted contract's notes drop out of the all-notes list.
        self.assertEqual(self.client.get(self.notes_all_url()).data['meta']['total_items'], 1)


class ContractPermissionTests(ContractAPITestCase):
    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_user(email='staff@example.com', password='Sup3r-secret!', full_name='Staff')
        self.client.force_authenticate(self.staff)

    def test_no_role_gets_403(self):
        self.assertEqual(self.client.get(self.list_url()).status_code, 403)

    def test_view_only_role_can_list_but_not_create(self):
        self.staff.roles.set([make_role(can_view=True)])
        self.assertEqual(self.client.get(self.list_url()).status_code, 200)
        self.assertEqual(self.client.post(self.create_url(), self.sample, format='json').status_code, 403)


class ContractCertificationTests(ContractAPITestCase):
    def test_new_contract_adds_a_certification_per_carrier_line(self):
        from apps.policies.models import Certification
        from apps.policies.utils import certification_due_date

        self.carrier.lines_of_business = ['Medicare Supplement', 'MAPD']
        self.carrier.save()
        response = self.client.post(self.create_url(), self.sample, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        rows = Certification.objects.filter(agent=self.agent, carrier=self.carrier).order_by('line_of_business')
        self.assertEqual([row.line_of_business for row in rows], ['MAPD', 'Medicare Supplement'])
        self.assertTrue(all(row.due_date == certification_due_date() for row in rows))
        self.assertTrue(all(row.created_by == self.admin for row in rows))
        self.assertEqual(rows[0].notes.get().kind, 'added')

    def test_failed_contract_adds_no_certification(self):
        from apps.policies.models import Certification

        response = self.client.post(self.create_url(), {**self.sample, 'appointed_states': ['LA']}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Certification.objects.exists())
