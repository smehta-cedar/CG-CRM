from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Role, RolePermission, User, UserNote
from .models.roles import PERMISSION_LABELS


class UserNotesTests(APITestCase):
    """The change notes the users API writes, and the roles list the form reads."""

    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='Sup3r-secret!', full_name='Admin')
        self.client.force_authenticate(self.admin)
        self.role = Role.objects.create(name='Staff')

    def url(self, name, *args):
        return reverse(f'accounts:apis:users:{name}', args=args)

    def test_create_records_added_note_with_password_redacted(self):
        response = self.client.post(
            self.url('create'),
            {'email': 'new@example.com', 'full_name': 'New User', 'password': 'Str0ng-pass-word!', 'role_id': str(self.role.pk)},
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        note = UserNote.objects.get(user_id=response.data['data']['id'])
        self.assertEqual(note.kind, 'added')
        self.assertEqual(
            note.changes,
            [
                {'field': 'name', 'from': '', 'to': 'New User'},
                {'field': 'email', 'from': '', 'to': 'new@example.com'},
                {'field': 'role', 'from': '', 'to': 'Staff'},
                {'field': 'status', 'from': '', 'to': 'active'},
                {'field': 'password', 'from': '', 'to': '', 'redacted': True},
            ],
        )

    def test_patch_block_and_set_password_record_notes(self):
        user = User.objects.create_user(email='u@example.com', password='Str0ng-pass-word!', full_name='U')
        self.client.patch(self.url('detail', user.pk), {'full_name': 'U Two'}, format='json')
        self.client.post(self.url('block', user.pk))
        self.client.post(self.url('unblock', user.pk))
        response = self.client.post(
            self.url('set-password', user.pk),
            {'new_password': 'An0ther-pass-word!', 'confirm_password': 'An0ther-pass-word!'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        response = self.client.get(self.url('notes', user.pk))
        self.assertEqual(response.status_code, 200)
        changes = [note['changes'] for note in response.data['data']]
        self.assertEqual(
            changes,
            [
                [{'field': 'password', 'from': '', 'to': '', 'redacted': True}],
                [{'field': 'status', 'from': 'inactive', 'to': 'active'}],
                [{'field': 'status', 'from': 'active', 'to': 'inactive'}],
                [{'field': 'name', 'from': 'U', 'to': 'U Two'}],
            ],
        )
        self.assertNotIn('An0ther', str(response.data))
        # The all-notes list holds the same four, newest first, paginated.
        response = self.client.get(self.url('notes-all'))
        self.assertEqual(response.data['meta']['total_items'], 4)

    def test_patch_without_change_writes_no_note(self):
        user = User.objects.create_user(email='u@example.com', password='Str0ng-pass-word!', full_name='U')
        self.client.patch(self.url('detail', user.pk), {'full_name': 'U'}, format='json')
        self.assertFalse(user.notes.exists())

    def test_roles_list(self):
        Role.objects.create(name='Admin')
        Role.objects.create(name='Old', is_active=False)
        response = self.client.get(reverse('accounts:apis:roles:list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([role['name'] for role in response.data['data']], ['Admin', 'Old', 'Staff'])
        # The Users form asks for the active ones only.
        response = self.client.get(reverse('accounts:apis:roles:list'), {'is_active': 'true'})
        self.assertEqual([role['name'] for role in response.data['data']], ['Admin', 'Staff'])


class RolesApiTests(APITestCase):
    """Roles are read by whoever may see users and changed by superusers only."""

    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='Sup3r-secret!', full_name='Admin')
        self.client.force_authenticate(self.admin)

    def url(self, name, *args):
        return reverse(f'accounts:apis:roles:{name}', args=args)

    def make_staff(self):
        """A non-superuser whose role may view users."""
        role = Role.objects.create(name='Staff')
        RolePermission.objects.create(role=role, module='users', can_view=True)
        return User.objects.create_user(email='staff@example.com', password='Str0ng-pass-word!', full_name='Staff', role=role)

    def test_create_with_permissions(self):
        response = self.client.post(
            self.url('create'),
            {
                'name': '  Ops  Manager ',
                'description': 'Runs the office.',
                'permissions': [
                    {'module': 'agents', 'can_view': True, 'can_create': True, 'can_update': True},
                    {'module': 'carriers', 'can_view': True},
                ],
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data['data']
        self.assertEqual(data['name'], 'Ops Manager')
        self.assertEqual(data['user_count'], 0)
        flags = {row['module']: row for row in data['permissions']}
        self.assertTrue(flags['agents']['can_update'])
        self.assertFalse(flags['agents']['can_delete'])
        self.assertTrue(flags['carriers']['can_view'])
        self.assertFalse(flags['carriers']['can_create'])
        # Every module is answered, the ones left out with no access.
        self.assertEqual(set(flags), set(PERMISSION_LABELS))
        self.assertFalse(any(flags['users'][f'can_{action}'] for action in ('view', 'create', 'update', 'delete')))
        role = Role.objects.get(pk=data['id'])
        holder = User.objects.create_user(email='ops@example.com', password='Str0ng-pass-word!', full_name='Ops', role=role)
        self.assertTrue(holder.has_permission('agents', 'create'))
        self.assertFalse(holder.has_permission('users', 'view'))

    def test_create_needs_view_for_other_actions(self):
        response = self.client.post(
            self.url('create'),
            {'name': 'Broken', 'permissions': [{'module': 'agents', 'can_delete': True}]},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('permissions', response.data['errors'])

    def test_create_rejects_duplicate_name_ignoring_case(self):
        Role.objects.create(name='Staff')
        response = self.client.post(self.url('create'), {'name': 'staff'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('name', response.data['errors'])

    def test_patch_replaces_permissions(self):
        role = Role.objects.create(name='Staff')
        RolePermission.objects.create(role=role, module='agents', can_view=True, can_delete=True)
        response = self.client.patch(
            self.url('detail', role.pk),
            {'name': 'Staff 2', 'permissions': [{'module': 'carriers', 'can_view': True}]},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        role.refresh_from_db()
        self.assertEqual(role.name, 'Staff 2')
        flags = {row['module']: row for row in response.data['data']['permissions']}
        self.assertFalse(flags['agents']['can_view'])
        self.assertTrue(flags['carriers']['can_view'])

    def test_delete_refused_while_users_hold_the_role(self):
        staff = self.make_staff()
        response = self.client.delete(self.url('detail', staff.role_id))
        self.assertEqual(response.status_code, 400)
        self.assertIn('still have this role', response.data['message'])
        staff.delete()
        response = self.client.delete(self.url('detail', staff.role_id))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(Role.objects.filter(pk=staff.role_id).exists())

    def test_non_superuser_can_read_but_not_change(self):
        staff = self.make_staff()
        self.client.force_authenticate(staff)
        self.assertEqual(self.client.get(self.url('list')).status_code, 200)
        self.assertEqual(self.client.get(self.url('detail', staff.role_id)).status_code, 200)
        self.assertEqual(self.client.get(self.url('modules')).status_code, 403)
        self.assertEqual(self.client.post(self.url('create'), {'name': 'Mine'}, format='json').status_code, 403)
        self.assertEqual(
            self.client.patch(self.url('detail', staff.role_id), {'name': 'Mine'}, format='json').status_code, 403
        )
        self.assertEqual(self.client.delete(self.url('detail', staff.role_id)).status_code, 403)

    def test_modules_and_user_count(self):
        staff = self.make_staff()
        response = self.client.get(self.url('modules'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([module['code'] for module in response.data['data']], list(PERMISSION_LABELS))
        response = self.client.get(self.url('detail', staff.role_id))
        self.assertEqual(response.data['data']['user_count'], 1)
