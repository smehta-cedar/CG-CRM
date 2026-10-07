from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Role, RolePermission, User
from apps.agency.models import Agency
from apps.agents.models import Agent
from apps.carriers.models import Carrier
from apps.contracts.models import AgencyCarrierContract

from .models import Password, PasswordNote


def make_role(**flags):
    role = Role.objects.create(name=f"passwords-{'-'.join(k for k, v in flags.items() if v) or 'none'}")
    RolePermission.objects.create(role=role, module='passwords', **flags)
    return role


class PasswordAPITestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='Sup3r-secret!', full_name='Admin')
        self.client.force_authenticate(self.admin)
        self.agent = Agent.objects.create(name='Maria Alva', npn='1')
        self.other_agent = Agent.objects.create(name='James Carter', npn='2')
        self.carrier = Carrier.objects.create(name='Humana', lines_of_business=['MAPD'])
        self.other_carrier = Carrier.objects.create(name='UHC', lines_of_business=['MAPD'])
        # Agents can only be given a carrier whose agency contract has a number.
        self.agency = Agency.objects.create(name='Cedar Grove')
        for carrier, number in ((self.carrier, 'A-1'), (self.other_carrier, 'A-2')):
            AgencyCarrierContract.objects.create(agency=self.agency, carrier=carrier, contract_number=number)
        self.sample = {
            'agent_id': str(self.agent.pk),
            'carrier_id': str(self.carrier.pk),
            'username': 'malva.agent',
            'portal_password': 'dummy pass 1 ',
        }

    def make_password(self, **overrides):
        fields = {
            'agent': self.agent,
            'carrier': self.carrier,
            'username': 'malva.agent',
            'portal_password': 'dummy-pass-1',
            **overrides,
        }
        return Password.objects.create(**fields)

    def list_url(self):
        return reverse('passwords:apis:passwords:list')

    def create_url(self):
        return reverse('passwords:apis:passwords:create')

    def detail_url(self, password):
        return reverse('passwords:apis:passwords:detail', args=[password.pk])

    def notes_url(self, password):
        return reverse('passwords:apis:passwords:notes', args=[password.pk])


class PasswordCreateTests(PasswordAPITestCase):
    def test_creates_password_keeping_it_as_typed(self):
        response = self.client.post(self.create_url(), self.sample, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data['data']
        self.assertEqual(data['agent'], {'id': str(self.agent.pk), 'name': 'Maria Alva', 'is_active': True})
        self.assertEqual(data['carrier']['name'], 'Humana')
        self.assertEqual(data['portal_password'], 'dummy pass 1 ')
        self.assertEqual(data['status'], 'active')

    def test_records_an_added_note_with_the_password_redacted(self):
        response = self.client.post(self.create_url(), self.sample, format='json')
        note = PasswordNote.objects.get(password_id=response.data['data']['id'])
        self.assertEqual(note.kind, 'added')
        self.assertEqual(
            note.changes,
            [
                {'field': 'agent', 'from': '', 'to': 'Maria Alva'},
                {'field': 'carrier', 'from': '', 'to': 'Humana'},
                {'field': 'username', 'from': '', 'to': 'malva.agent'},
                {'field': 'password', 'from': '', 'to': '', 'redacted': True},
                {'field': 'status', 'from': '', 'to': 'active'},
            ],
        )

    def test_saves_link_and_notes_it(self):
        response = self.client.post(
            self.create_url(), {**self.sample, 'link': 'https://agent.humana.com'}, format='json'
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['data']['link'], 'https://agent.humana.com')
        note = PasswordNote.objects.get(password_id=response.data['data']['id'])
        self.assertIn({'field': 'link', 'from': '', 'to': 'https://agent.humana.com'}, note.changes)

    def test_rejects_invalid_link(self):
        response = self.client.post(self.create_url(), {**self.sample, 'link': 'not a url'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('link', response.data['errors'])

    def test_rejects_blank_password(self):
        response = self.client.post(self.create_url(), {**self.sample, 'portal_password': '   '}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('portal_password', response.data['errors'])

    def test_rejects_second_password_for_same_pair(self):
        self.make_password()
        response = self.client.post(self.create_url(), self.sample, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['carrier_id'], ['Maria Alva already has a password at Humana.'])

    def test_rejects_unknown_agent(self):
        response = self.client.post(
            self.create_url(), {**self.sample, 'agent_id': '00000000-0000-0000-0000-000000000000'}, format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('agent_id', response.data['errors'])


class PasswordListTests(PasswordAPITestCase):
    def test_lists_by_agent_then_carrier(self):
        self.make_password(agent=self.other_agent, carrier=self.other_carrier)
        self.make_password(carrier=self.other_carrier)
        self.make_password()
        response = self.client.get(self.list_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [(p['agent']['name'], p['carrier']['name']) for p in response.data['data']],
            [('James Carter', 'UHC'), ('Maria Alva', 'Humana'), ('Maria Alva', 'UHC')],
        )

    def test_filters(self):
        self.make_password(agent=self.other_agent, status='pending')
        self.make_password()
        response = self.client.get(self.list_url(), {'carrier_id': str(self.carrier.pk), 'status': 'pending'})
        self.assertEqual([p['agent']['name'] for p in response.data['data']], ['James Carter'])
        response = self.client.get(self.list_url(), {'search': 'maria'})
        self.assertEqual([p['agent']['name'] for p in response.data['data']], ['Maria Alva'])


class AgencyPasswordTests(PasswordAPITestCase):
    def agency_sample(self, **overrides):
        return {
            'agency_id': str(self.agency.pk),
            'carrier_id': str(self.carrier.pk),
            'username': 'cedar.agency',
            'portal_password': 'agency-pass',
            **overrides,
        }

    def test_creates_agency_password(self):
        response = self.client.post(self.create_url(), self.agency_sample(), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data['data']
        self.assertIsNone(data['agent'])
        self.assertEqual(data['agency']['name'], 'Cedar Grove')
        note = PasswordNote.objects.get(password_id=data['id'])
        self.assertIn({'field': 'agent', 'from': '', 'to': 'Cedar Grove'}, note.changes)

    def test_agency_password_needs_no_contract_number(self):
        AgencyCarrierContract.objects.filter(carrier=self.carrier).update(contract_number='')
        response = self.client.post(self.create_url(), self.agency_sample(), format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def test_rejects_second_agency_password_at_carrier(self):
        self.client.post(self.create_url(), self.agency_sample(), format='json')
        response = self.client.post(self.create_url(), self.agency_sample(username='other'), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('carrier_id', response.data['errors'])

    def test_agency_and_agent_can_share_a_carrier(self):
        self.make_password()
        response = self.client.post(self.create_url(), self.agency_sample(), format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def test_rejects_both_agent_and_agency(self):
        response = self.client.post(
            self.create_url(), self.agency_sample(agent_id=str(self.agent.pk)), format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('agent_id', response.data['errors'])

    def test_rejects_neither_agent_nor_agency(self):
        sample = {key: value for key, value in self.sample.items() if key != 'agent_id'}
        response = self.client.post(self.create_url(), sample, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('agent_id', response.data['errors'])

    def test_patch_moves_agent_password_to_agency(self):
        password = self.make_password()
        response = self.client.patch(
            self.detail_url(password), {'agency_id': str(self.agency.pk)}, format='json'
        )
        self.assertEqual(response.status_code, 200, response.data)
        password.refresh_from_db()
        self.assertIsNone(password.agent)
        self.assertEqual(password.agency, self.agency)

    def test_list_filters_by_agency(self):
        self.make_password()
        self.make_password(agent=None, agency=self.agency, username='cedar.agency')
        response = self.client.get(self.list_url(), {'agency_id': str(self.agency.pk)})
        self.assertEqual([row['username'] for row in response.data['data']], ['cedar.agency'])


class PasswordDetailTests(PasswordAPITestCase):
    def test_patch_records_note_with_names(self):
        password = self.make_password()
        response = self.client.patch(
            self.detail_url(password),
            {'carrier_id': str(self.other_carrier.pk), 'portal_password': 'new', 'status': 'pending'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['carrier']['name'], 'UHC')
        self.assertEqual(
            password.notes.get().changes,
            [
                {'field': 'carrier', 'from': 'Humana', 'to': 'UHC'},
                {'field': 'password', 'from': '', 'to': '', 'redacted': True},
                {'field': 'status', 'from': 'active', 'to': 'pending'},
            ],
        )

    def test_patch_rejects_move_onto_taken_pair(self):
        self.make_password(carrier=self.other_carrier)
        password = self.make_password()
        response = self.client.patch(self.detail_url(password), {'carrier_id': str(self.other_carrier.pk)}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('carrier_id', response.data['errors'])

    def test_patch_without_change_writes_no_note(self):
        password = self.make_password()
        response = self.client.patch(self.detail_url(password), {'username': 'malva.agent'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(password.notes.exists())

    def test_delete_frees_the_pair(self):
        password = self.make_password()
        self.assertEqual(self.client.delete(self.detail_url(password)).status_code, 200)
        self.assertEqual(self.client.post(self.create_url(), self.sample, format='json').status_code, 201)

    def test_notes_never_hold_the_password(self):
        password = self.make_password()
        self.client.patch(self.detail_url(password), {'portal_password': 'secret-value'}, format='json')
        response = self.client.get(self.notes_url(password))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('secret-value', str(response.data))
        self.assertTrue(response.data['data'][0]['changes'][0]['redacted'])


class PasswordCarrierAccessTests(PasswordAPITestCase):
    MESSAGE = ['Add a contract number before an agent can use this carrier.']

    def test_rejects_carrier_whose_agency_contract_has_no_number(self):
        AgencyCarrierContract.objects.filter(carrier=self.carrier).update(contract_number='')
        response = self.client.post(self.create_url(), self.sample, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['carrier'], self.MESSAGE)

    def test_edit_keeping_an_inaccessible_carrier_is_allowed(self):
        password = self.make_password()
        AgencyCarrierContract.objects.filter(carrier=self.carrier).delete()
        response = self.client.patch(
            self.detail_url(password),
            {'carrier_id': str(self.carrier.pk), 'username': 'maria.a'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)

    def test_edit_moving_to_an_inaccessible_carrier_is_rejected(self):
        password = self.make_password()
        AgencyCarrierContract.objects.filter(carrier=self.other_carrier).update(contract_number='')
        response = self.client.patch(self.detail_url(password), {'carrier_id': str(self.other_carrier.pk)}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['carrier'], self.MESSAGE)


class PasswordPermissionTests(PasswordAPITestCase):
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
