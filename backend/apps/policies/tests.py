from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Role, RolePermission, User
from apps.agency.models import Agency
from apps.carriers.models import Carrier
from apps.contracts.models import AgencyCarrierContract

from .models import PolicyType, PolicyTypeNote

SAMPLE = {
    'name': 'Medicare Advantage',
    'certification_scope': 'single',
}


def make_policy_type(**overrides):
    return PolicyType.objects.create(**{**SAMPLE, **overrides})


def make_role(**flags):
    role = Role.objects.create(name=f"policy-types-{'-'.join(k for k, v in flags.items() if v) or 'none'}")
    RolePermission.objects.create(role=role, module='policy_types', **flags)
    return role


class PolicyTypeAPITestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='Sup3r-secret!', full_name='Admin')
        self.client.force_authenticate(self.admin)

    def list_url(self):
        return reverse('policies:apis:policy_types:list')

    def create_url(self):
        return reverse('policies:apis:policy_types:create')

    def detail_url(self, policy_type):
        return reverse('policies:apis:policy_types:detail', args=[policy_type.pk])

    def notes_url(self, policy_type):
        return reverse('policies:apis:policy_types:notes', args=[policy_type.pk])


class PolicyTypeCreateTests(PolicyTypeAPITestCase):
    def test_creates_policy_type_from_sample(self):
        response = self.client.post(self.create_url(), SAMPLE, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data['data']
        self.assertEqual(data['name'], 'Medicare Advantage')
        self.assertEqual(data['certification_scope'], 'single')
        self.assertEqual(data['certification_carriers'], [])
        self.assertTrue(data['is_active'])
        policy_type = PolicyType.objects.get(pk=data['id'])
        self.assertEqual(policy_type.created_by, self.admin)

    def test_certification_defaults_to_off(self):
        response = self.client.post(self.create_url(), {'name': 'Dental'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['data']['certification_scope'], 'none')

    def test_records_an_added_note(self):
        response = self.client.post(self.create_url(), SAMPLE, format='json')
        note = PolicyTypeNote.objects.get(policy_type_id=response.data['data']['id'])
        self.assertEqual(note.kind, 'added')
        self.assertEqual(note.created_by, self.admin)
        self.assertEqual(
            note.changes,
            [
                {'field': 'name', 'from': '', 'to': 'Medicare Advantage'},
                {'field': 'certification_scope', 'from': '', 'to': 'single'},
                {'field': 'status', 'from': '', 'to': 'active'},
            ],
        )

    def test_name_is_required(self):
        response = self.client.post(self.create_url(), {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('name', response.data['errors'])

    def test_name_is_trimmed(self):
        response = self.client.post(self.create_url(), {'name': '  Final   Expense '}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['data']['name'], 'Final Expense')

    def test_rejects_duplicate_name_case_insensitively(self):
        make_policy_type()
        response = self.client.post(self.create_url(), {**SAMPLE, 'name': 'MEDICARE ADVANTAGE'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('name', response.data['errors'])

    def test_deleted_policy_types_name_can_be_reused(self):
        make_policy_type().delete()
        response = self.client.post(self.create_url(), SAMPLE, format='json')
        self.assertEqual(response.status_code, 201, response.data)


class PolicyTypeListTests(PolicyTypeAPITestCase):
    def test_lists_policy_types_by_name(self):
        make_policy_type(name='Term Life', certification_scope='none')
        make_policy_type()
        response = self.client.get(self.list_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual([p['name'] for p in response.data['data']], ['Medicare Advantage', 'Term Life'])
        self.assertEqual(response.data['meta']['total_items'], 2)

    def test_search_matches_name(self):
        make_policy_type(name='Term Life', certification_scope='none')
        make_policy_type()
        response = self.client.get(self.list_url(), {'search': 'term'})
        self.assertEqual([p['name'] for p in response.data['data']], ['Term Life'])

    def test_filters_by_certification_and_is_active(self):
        make_policy_type(name='Term Life', certification_scope='none', is_active=False)
        make_policy_type()
        response = self.client.get(self.list_url(), {'certification_scope': 'single'})
        self.assertEqual([p['name'] for p in response.data['data']], ['Medicare Advantage'])
        response = self.client.get(self.list_url(), {'is_active': 'false'})
        self.assertEqual([p['name'] for p in response.data['data']], ['Term Life'])

    def test_hides_deleted_policy_types(self):
        make_policy_type().delete()
        response = self.client.get(self.list_url())
        self.assertEqual(response.data['data'], [])


class PolicyTypeDetailTests(PolicyTypeAPITestCase):
    def test_get(self):
        policy_type = make_policy_type()
        response = self.client.get(self.detail_url(policy_type))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['name'], 'Medicare Advantage')

    def test_patch_updates_flag_and_records_note(self):
        policy_type = make_policy_type()
        response = self.client.patch(
            self.detail_url(policy_type), {'certification_scope': 'none', 'is_active': False}, format='json'
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['certification_scope'], 'none')
        self.assertFalse(response.data['data']['is_active'])
        note = policy_type.notes.get()
        self.assertEqual(note.kind, 'edited')
        self.assertEqual(
            note.changes,
            [
                {'field': 'certification_scope', 'from': 'single', 'to': 'none'},
                {'field': 'status', 'from': 'active', 'to': 'inactive'},
            ],
        )

    def test_patch_with_no_change_writes_no_note(self):
        policy_type = make_policy_type()
        response = self.client.patch(self.detail_url(policy_type), {'name': 'Medicare Advantage'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(policy_type.notes.exists())

    def test_patch_keeps_own_name(self):
        policy_type = make_policy_type()
        response = self.client.patch(self.detail_url(policy_type), {'name': 'MEDICARE ADVANTAGE'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['name'], 'MEDICARE ADVANTAGE')

    def test_patch_rejects_another_policy_types_name(self):
        make_policy_type(name='Term Life')
        policy_type = make_policy_type()
        response = self.client.patch(self.detail_url(policy_type), {'name': 'term life'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('name', response.data['errors'])

    def test_delete_is_soft(self):
        policy_type = make_policy_type()
        response = self.client.delete(self.detail_url(policy_type))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PolicyType.objects.filter(pk=policy_type.pk).exists())
        self.assertTrue(PolicyType.all_objects.filter(pk=policy_type.pk).exists())
        self.assertEqual(self.client.get(self.detail_url(policy_type)).status_code, 404)

    def test_notes_newest_first(self):
        policy_type = make_policy_type()
        self.client.patch(self.detail_url(policy_type), {'name': 'MA'}, format='json')
        self.client.patch(self.detail_url(policy_type), {'name': 'MAPD'}, format='json')
        response = self.client.get(self.notes_url(policy_type))
        self.assertEqual(response.status_code, 200)
        notes = response.data['data']
        self.assertEqual(len(notes), 2)
        self.assertEqual(notes[0]['changes'], [{'field': 'name', 'from': 'MA', 'to': 'MAPD'}])
        self.assertEqual(notes[0]['created_by'], 'Admin')


class PolicyTypeCertificationCarrierTests(PolicyTypeAPITestCase):
    def setUp(self):
        super().setUp()
        agency = Agency.objects.create(name='Cedar Grove')
        self.humana = Carrier.objects.create(name='Humana', lines_of_business=['MAPD'])
        self.aetna = Carrier.objects.create(name='Aetna', lines_of_business=['MAPD'])
        self.cigna = Carrier.objects.create(name='Cigna', lines_of_business=['MAPD'])
        # Cigna has no agency contract; a blank contract number still counts as one.
        AgencyCarrierContract.objects.create(agency=agency, carrier=self.humana, contract_number='A-1')
        AgencyCarrierContract.objects.create(agency=agency, carrier=self.aetna)

    def per_carrier(self, *carriers):
        return {
            'name': 'MAPD',
            'certification_scope': 'per_carrier',
            'certification_carriers': [str(carrier.pk) for carrier in carriers],
        }

    def test_creates_per_carrier_type_with_carriers_by_name(self):
        response = self.client.post(self.create_url(), self.per_carrier(self.humana, self.aetna), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data['data']
        self.assertEqual(data['certification_scope'], 'per_carrier')
        self.assertEqual([carrier['name'] for carrier in data['certification_carriers']], ['Aetna', 'Humana'])
        note = PolicyTypeNote.objects.get(policy_type_id=data['id'])
        self.assertIn({'field': 'certification_scope', 'from': '', 'to': 'per carrier'}, note.changes)
        self.assertIn({'field': 'certification_carriers', 'from': '', 'to': 'Aetna, Humana'}, note.changes)
        # Reading it back gives the same carriers.
        response = self.client.get(self.detail_url(PolicyType.objects.get(pk=data['id'])))
        self.assertEqual(
            [carrier['name'] for carrier in response.data['data']['certification_carriers']], ['Aetna', 'Humana']
        )

    def test_per_carrier_needs_a_carrier(self):
        response = self.client.post(self.create_url(), self.per_carrier(), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('certification_carriers', response.data['errors'])

    def test_uncontracted_carrier_is_400(self):
        response = self.client.post(self.create_url(), self.per_carrier(self.humana, self.cigna), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['certification_carriers'], ['Cigna has no agency contract.'])

    def test_deleted_contract_does_not_count(self):
        AgencyCarrierContract.objects.get(carrier=self.aetna).delete()
        response = self.client.post(self.create_url(), self.per_carrier(self.aetna), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('certification_carriers', response.data['errors'])

    def test_carriers_on_single_scope_are_400(self):
        body = {**self.per_carrier(self.humana), 'certification_scope': 'single'}
        response = self.client.post(self.create_url(), body, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('certification_carriers', response.data['errors'])

    def test_unknown_scope_is_400(self):
        response = self.client.post(self.create_url(), {'name': 'MAPD', 'certification_scope': 'both'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('certification_scope', response.data['errors'])

    def test_patch_changes_carriers_and_notes_them(self):
        policy_type = make_policy_type(name='MAPD', certification_scope='per_carrier')
        policy_type.certification_carriers.set([self.humana])
        body = {'certification_carriers': [str(self.humana.pk), str(self.aetna.pk)]}
        response = self.client.patch(self.detail_url(policy_type), body, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data['data']['certification_carriers']), 2)
        self.assertEqual(
            policy_type.notes.get().changes,
            [{'field': 'certification_carriers', 'from': 'Humana', 'to': 'Aetna, Humana'}],
        )

    def test_patch_to_per_carrier_needs_carriers(self):
        policy_type = make_policy_type(name='MAPD')
        response = self.client.patch(self.detail_url(policy_type), {'certification_scope': 'per_carrier'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('certification_carriers', response.data['errors'])

    def test_patch_leaving_per_carrier_clears_carriers(self):
        policy_type = make_policy_type(name='MAPD', certification_scope='per_carrier')
        policy_type.certification_carriers.set([self.humana])
        response = self.client.patch(self.detail_url(policy_type), {'certification_scope': 'single'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['certification_carriers'], [])
        self.assertEqual(
            policy_type.notes.get().changes,
            [
                {'field': 'certification_scope', 'from': 'per carrier', 'to': 'single'},
                {'field': 'certification_carriers', 'from': 'Humana', 'to': ''},
            ],
        )

    def test_patch_name_only_keeps_carriers(self):
        policy_type = make_policy_type(name='MAPD', certification_scope='per_carrier')
        policy_type.certification_carriers.set([self.humana])
        response = self.client.patch(self.detail_url(policy_type), {'name': 'MA-PD'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data['data']['certification_carriers']), 1)


class PolicyTypePermissionTests(PolicyTypeAPITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(email='staff@example.com', password='Sup3r-secret!', full_name='Staff')
        self.client.force_authenticate(self.staff)

    def test_anonymous_gets_401(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.list_url()).status_code, 401)

    def test_no_role_gets_403(self):
        self.assertEqual(self.client.get(self.list_url()).status_code, 403)

    def test_view_only_role_can_list_but_not_create(self):
        self.staff.role = make_role(can_view=True)
        self.staff.save()
        self.assertEqual(self.client.get(self.list_url()).status_code, 200)
        self.assertEqual(self.client.post(self.create_url(), SAMPLE, format='json').status_code, 403)

    def test_create_role_can_create(self):
        self.staff.role = make_role(can_view=True, can_create=True)
        self.staff.save()
        self.assertEqual(self.client.post(self.create_url(), SAMPLE, format='json').status_code, 201)
