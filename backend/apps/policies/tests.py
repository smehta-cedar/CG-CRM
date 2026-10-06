from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Role, RolePermission, User

from .models import PolicyType, PolicyTypeNote

SAMPLE = {
    'name': 'Medicare Advantage',
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
        self.assertNotIn('certification_scope', data)
        self.assertTrue(data['is_active'])
        policy_type = PolicyType.objects.get(pk=data['id'])
        self.assertEqual(policy_type.created_by, self.admin)

    def test_records_an_added_note(self):
        response = self.client.post(self.create_url(), SAMPLE, format='json')
        note = PolicyTypeNote.objects.get(policy_type_id=response.data['data']['id'])
        self.assertEqual(note.kind, 'added')
        self.assertEqual(note.created_by, self.admin)
        self.assertEqual(
            note.changes,
            [
                {'field': 'name', 'from': '', 'to': 'Medicare Advantage'},
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
        make_policy_type(name='Term Life')
        make_policy_type()
        response = self.client.get(self.list_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual([p['name'] for p in response.data['data']], ['Medicare Advantage', 'Term Life'])
        self.assertEqual(response.data['meta']['total_items'], 2)

    def test_search_matches_name(self):
        make_policy_type(name='Term Life')
        make_policy_type()
        response = self.client.get(self.list_url(), {'search': 'term'})
        self.assertEqual([p['name'] for p in response.data['data']], ['Term Life'])

    def test_filters_by_is_active(self):
        make_policy_type(name='Term Life', is_active=False)
        make_policy_type()
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

    def test_patch_updates_status_and_records_note(self):
        policy_type = make_policy_type()
        response = self.client.patch(self.detail_url(policy_type), {'is_active': False}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data['data']['is_active'])
        note = policy_type.notes.get()
        self.assertEqual(note.kind, 'edited')
        self.assertEqual(note.changes, [{'field': 'status', 'from': 'active', 'to': 'inactive'}])

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
        self.staff.roles.set([make_role(can_view=True)])
        self.assertEqual(self.client.get(self.list_url()).status_code, 200)
        self.assertEqual(self.client.post(self.create_url(), SAMPLE, format='json').status_code, 403)

    def test_create_role_can_create(self):
        self.staff.roles.set([make_role(can_view=True, can_create=True)])
        self.assertEqual(self.client.post(self.create_url(), SAMPLE, format='json').status_code, 201)
