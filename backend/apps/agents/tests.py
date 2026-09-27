from datetime import date

from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Role, RolePermission, User
from apps.agency.models import State

from .models import Agent, AgentNote, AgentStateLicense

SAMPLE = {
    'name': 'Maria Alva',
    'aliases': ['Maria Lopez'],
    'npn': '17654321',
    'email': 'maria.alvarez@example.com',
    'phone': '(555)010-2231',
    'personal_email': 'maria.alva@example.net',
    'address': {'street': '1420 Cedar Grove Ln', 'city': 'Austin', 'state': 'TX', 'zip': '78704'},
    'licenses': [{'state': 'TX', 'license_number': '2104587'}, {'state': 'FL', 'license_number': 'W482913'}],
}


def make_agent(**overrides):
    fields = {**SAMPLE, **overrides}
    licenses = fields.pop('licenses', [])
    address = fields.pop('address', None) or {}
    agent = Agent.objects.create(
        **fields,
        address_street=address.get('street', ''),
        address_city=address.get('city', ''),
        address_state=address.get('state', ''),
        address_zip=address.get('zip', ''),
    )
    for item in licenses:
        AgentStateLicense.objects.create(
            agent=agent,
            state=State.objects.get(code=item['state']),
            license_number=item.get('license_number', ''),
            life=item.get('life', False),
            health=item.get('health', False),
            start_date=date(2024, 1, 1),
            end_date=date(2026, 1, 1),
        )
    return agent


def make_role(**flags):
    role = Role.objects.create(name=f"agents-{'-'.join(k for k, v in flags.items() if v) or 'none'}")
    RolePermission.objects.create(role=role, module='agents', **flags)
    return role


class AgentAPITestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='Sup3r-secret!', full_name='Admin')
        self.client.force_authenticate(self.admin)

    def list_url(self):
        return reverse('agents:apis:agents:list')

    def create_url(self):
        return reverse('agents:apis:agents:create')

    def detail_url(self, agent):
        return reverse('agents:apis:agents:detail', args=[agent.pk])

    def notes_url(self, agent):
        return reverse('agents:apis:agents:notes', args=[agent.pk])


class AgentCreateTests(AgentAPITestCase):
    def test_creates_agent_from_sample(self):
        response = self.client.post(self.create_url(), SAMPLE, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data['data']
        self.assertEqual(data['name'], 'Maria Alva')
        self.assertEqual(data['npn'], '17654321')
        self.assertEqual(data['address'], SAMPLE['address'])
        self.assertEqual(data['personal_phone'], '')
        # Licences come back in state-code order, active, running two years from today.
        self.assertEqual([row['state'] for row in data['licenses']], ['FL', 'TX'])
        self.assertEqual(data['licenses'][1]['license_number'], '2104587')
        self.assertEqual(data['licenses'][1]['status'], 'active')
        self.assertEqual(data['licenses'][1]['start_date'], date.today().isoformat())
        self.assertEqual(data['licenses'][1]['end_date'][:4], str(date.today().year + 2))
        self.assertTrue(data['is_active'])

    def test_records_an_added_note(self):
        response = self.client.post(self.create_url(), SAMPLE, format='json')
        note = AgentNote.objects.get(agent_id=response.data['data']['id'])
        self.assertEqual(note.kind, 'added')
        fields = [change['field'] for change in note.changes]
        self.assertEqual(
            fields,
            ['name', 'aliases', 'status', 'npn', 'email', 'phone', 'personal_email', 'address', 'licensed_states', 'license_numbers'],
        )
        by_field = {change['field']: change['to'] for change in note.changes}
        self.assertEqual(by_field['address'], '1420 Cedar Grove Ln, Austin, TX 78704')
        self.assertEqual(by_field['licensed_states'], 'FL, TX')
        self.assertEqual(by_field['license_numbers'], 'FL W482913, TX 2104587')

    def test_name_and_npn_are_required(self):
        response = self.client.post(self.create_url(), {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('name', response.data['errors'])
        self.assertIn('npn', response.data['errors'])

    def test_npn_must_be_digits(self):
        response = self.client.post(self.create_url(), {'name': 'X', 'npn': 'abc'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('npn', response.data['errors'])

    def test_rejects_duplicate_npn_naming_the_owner(self):
        make_agent()
        response = self.client.post(self.create_url(), {'name': 'Other', 'npn': SAMPLE['npn']}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['npn'], ['NPN 17654321 already belongs to Maria Alva.'])

    def test_rejects_partial_address(self):
        response = self.client.post(
            self.create_url(),
            {'name': 'X', 'npn': '1', 'address': {'street': '1 Main', 'city': '', 'state': '', 'zip': ''}},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('address', response.data['errors'])

    def test_blank_address_is_none(self):
        response = self.client.post(
            self.create_url(),
            {'name': 'X', 'npn': '1', 'address': {'street': '', 'city': '', 'state': '', 'zip': ''}},
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNone(response.data['data']['address'])

    def test_rejects_unknown_license_state(self):
        response = self.client.post(
            self.create_url(), {'name': 'X', 'npn': '1', 'licenses': [{'state': 'ZZ'}]}, format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('licenses', response.data['errors'])

    def test_deleted_agents_npn_can_be_reused(self):
        make_agent().delete()
        response = self.client.post(self.create_url(), SAMPLE, format='json')
        self.assertEqual(response.status_code, 201, response.data)


class AgentListTests(AgentAPITestCase):
    def test_lists_by_name(self):
        make_agent(name='Zed', npn='2', aliases=[], licenses=[])
        make_agent()
        response = self.client.get(self.list_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual([a['name'] for a in response.data['data']], ['Maria Alva', 'Zed'])

    def test_search_and_state_filter(self):
        make_agent(name='Zed', npn='2', aliases=['Zee'], licenses=[{'state': 'CA'}])
        make_agent()
        response = self.client.get(self.list_url(), {'search': 'zee'})
        self.assertEqual([a['name'] for a in response.data['data']], ['Zed'])
        response = self.client.get(self.list_url(), {'state': 'tx'})
        self.assertEqual([a['name'] for a in response.data['data']], ['Maria Alva'])


class AgentDetailTests(AgentAPITestCase):
    def test_patch_syncs_licenses_and_records_note(self):
        agent = make_agent()
        tx_row = agent.licenses.get(state__code='TX')
        response = self.client.patch(
            self.detail_url(agent),
            {'licenses': [{'state': 'TX', 'license_number': '999'}, {'state': 'CA', 'license_number': 'C1'}]},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        rows = response.data['data']['licenses']
        self.assertEqual([(row['state'], row['license_number']) for row in rows], [('CA', 'C1'), ('TX', '999')])
        # TX kept its row (same id, dates untouched); FL's row is soft-deleted.
        tx_row.refresh_from_db()
        self.assertEqual(tx_row.license_number, '999')
        self.assertEqual(tx_row.start_date, date(2024, 1, 1))
        self.assertTrue(AgentStateLicense.all_objects.filter(agent=agent, state__code='FL', deleted_at__isnull=False).exists())
        note = agent.notes.get()
        self.assertEqual(
            note.changes,
            [
                {'field': 'licensed_states', 'from': 'FL, TX', 'to': 'CA, TX'},
                {'field': 'license_numbers', 'from': 'FL W482913, TX 2104587', 'to': 'CA C1, TX 999'},
            ],
        )

    def test_patch_sets_license_lines_and_records_note(self):
        agent = make_agent(licenses=[{'state': 'TX', 'license_number': '2104587', 'life': True}])
        response = self.client.patch(
            self.detail_url(agent),
            {
                'licenses': [
                    {'state': 'TX', 'license_number': '2104587', 'life': True, 'health': True},
                    {'state': 'FL', 'license_number': 'W482913', 'health': True},
                ]
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        rows = response.data['data']['licenses']
        self.assertEqual(
            [(row['state'], row['life'], row['health']) for row in rows],
            [('FL', False, True), ('TX', True, True)],
        )
        # The lines are listed on the note; a state with none ticked is left out.
        note = agent.notes.get()
        self.assertIn({'field': 'license_lines', 'from': 'TX Life', 'to': 'FL Health, TX Life & Health'}, note.changes)

        # Sending a state without its lines switches them off.
        response = self.client.patch(
            self.detail_url(agent), {'licenses': [{'state': 'TX', 'license_number': '2104587'}]}, format='json'
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([(row['life'], row['health']) for row in response.data['data']['licenses']], [(False, False)])

    def test_patch_without_change_writes_no_note(self):
        agent = make_agent()
        response = self.client.patch(self.detail_url(agent), {'name': 'Maria Alva'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(agent.notes.exists())

    def test_patch_clears_address_with_null(self):
        agent = make_agent()
        response = self.client.patch(self.detail_url(agent), {'address': None}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.data['data']['address'])
        self.assertEqual(agent.notes.get().changes[0]['field'], 'address')

    def test_patch_rejects_another_agents_npn(self):
        make_agent(name='Zed', npn='2', licenses=[])
        agent = make_agent()
        response = self.client.patch(self.detail_url(agent), {'npn': '2'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('npn', response.data['errors'])

    def test_delete_is_soft(self):
        agent = make_agent()
        self.assertEqual(self.client.delete(self.detail_url(agent)).status_code, 200)
        self.assertFalse(Agent.objects.filter(pk=agent.pk).exists())
        self.assertTrue(Agent.all_objects.filter(pk=agent.pk).exists())

    def test_notes_endpoint(self):
        agent = make_agent()
        self.client.patch(self.detail_url(agent), {'is_active': False}, format='json')
        response = self.client.get(self.notes_url(agent))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data'][0]['changes'], [{'field': 'status', 'from': 'active', 'to': 'inactive'}])
        self.assertEqual(response.data['data'][0]['created_by'], 'Admin')


class AgentPermissionTests(AgentAPITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(email='staff@example.com', password='Sup3r-secret!', full_name='Staff')
        self.client.force_authenticate(self.staff)

    def test_no_role_gets_403(self):
        self.assertEqual(self.client.get(self.list_url()).status_code, 403)

    def test_view_only_role_can_list_but_not_create(self):
        self.staff.role = make_role(can_view=True)
        self.staff.save()
        self.assertEqual(self.client.get(self.list_url()).status_code, 200)
        self.assertEqual(self.client.post(self.create_url(), SAMPLE, format='json').status_code, 403)
