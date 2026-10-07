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
            {'email': 'new@example.com', 'full_name': 'New User', 'password': 'Str0ng-pass-word!', 'role_ids': [str(self.role.pk)]},
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
                {'field': 'roles', 'from': '', 'to': 'Staff'},
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

    def test_user_holds_several_roles(self):
        ops = Role.objects.create(name='Ops')
        response = self.client.post(
            self.url('create'),
            {
                'email': 'two@example.com',
                'full_name': 'Two Roles',
                'password': 'Str0ng-pass-word!',
                'role_ids': [str(self.role.pk), str(ops.pk)],
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(sorted(role['name'] for role in response.data['data']['roles']), ['Ops', 'Staff'])
        user_id = response.data['data']['id']

        # Search matching both roles still lists the user once; ?role_id= matches either role.
        response = self.client.get(self.url('list'), {'search': 's'})
        self.assertEqual([user['id'] for user in response.data['data']].count(user_id), 1)
        for role in (self.role, ops):
            response = self.client.get(self.url('list'), {'role_id': str(role.pk)})
            self.assertIn(user_id, [user['id'] for user in response.data['data']])

        # The sent list replaces the roles; [] removes them all.
        response = self.client.patch(self.url('detail', user_id), {'role_ids': [str(ops.pk)]}, format='json')
        self.assertEqual([role['name'] for role in response.data['data']['roles']], ['Ops'])
        response = self.client.patch(self.url('detail', user_id), {'role_ids': []}, format='json')
        self.assertEqual(response.data['data']['roles'], [])
        changes = [note.changes for note in UserNote.objects.filter(user_id=user_id, kind='edited')]
        self.assertIn([{'field': 'roles', 'from': 'Ops, Staff', 'to': 'Ops'}], changes)
        self.assertIn([{'field': 'roles', 'from': 'Ops', 'to': ''}], changes)

    def test_inactive_role_cannot_be_assigned(self):
        off = Role.objects.create(name='Off', is_active=False)
        user = User.objects.create_user(email='u@example.com', password='Str0ng-pass-word!', full_name='U')
        response = self.client.patch(self.url('detail', user.pk), {'role_ids': [str(off.pk)]}, format='json')
        self.assertEqual(response.status_code, 400)

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


class UserManagerLimitsTests(APITestCase):
    """What someone with every `users` action may do short of being a superuser."""

    def setUp(self):
        manage = Role.objects.create(name='User manager')
        RolePermission.objects.create(
            role=manage, module='users', can_view=True, can_create=True, can_update=True, can_delete=True
        )
        self.manager = User.objects.create_user(email='hr@example.com', password='Str0ng-pass-word!', full_name='HR')
        self.manager.roles.add(manage)
        self.admin_role = Role.objects.create(name='Admin')
        self.client.force_authenticate(self.manager)

    def url(self, name, *args):
        return reverse(f'accounts:apis:users:{name}', args=args)

    def make_user(self, *roles):
        user = User.objects.create_user(email='u@example.com', password='Str0ng-pass-word!', full_name='U')
        user.roles.add(*roles)
        return user

    def test_cannot_create_a_user_with_roles(self):
        body = {'email': 'new@example.com', 'full_name': 'New', 'password': 'Str0ng-pass-word!'}
        response = self.client.post(self.url('create'), {**body, 'role_ids': [str(self.admin_role.pk)]}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(email='new@example.com').exists())
        # Without roles, or with an empty list, the user is created with no access.
        response = self.client.post(self.url('create'), {**body, 'role_ids': []}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['data']['roles'], [])

    def test_cannot_change_anyones_roles(self):
        user = self.make_user()
        for target in (user, self.manager):
            response = self.client.patch(
                self.url('detail', target.pk), {'role_ids': [str(self.admin_role.pk)]}, format='json'
            )
            self.assertEqual(response.status_code, 403)
            self.assertFalse(target.roles.filter(pk=self.admin_role.pk).exists())

    def test_can_edit_other_fields_and_resend_same_roles(self):
        user = self.make_user(self.admin_role)
        response = self.client.patch(
            self.url('detail', user.pk),
            {'full_name': 'U Two', 'phone': '555', 'role_ids': [str(self.admin_role.pk)]},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['full_name'], 'U Two')
        self.assertEqual(self.client.post(self.url('block', user.pk)).status_code, 200)
        self.assertEqual(self.client.post(self.url('unblock', user.pk)).status_code, 200)

    def test_cannot_set_a_password(self):
        user = self.make_user(self.admin_role)
        body = {'new_password': 'An0ther-pass-word!', 'confirm_password': 'An0ther-pass-word!'}
        for target in (user, self.manager):
            self.assertEqual(self.client.post(self.url('set-password', target.pk), body, format='json').status_code, 403)
        user.refresh_from_db()
        self.assertTrue(user.check_password('Str0ng-pass-word!'))

    def test_superuser_can_do_both(self):
        admin = User.objects.create_superuser(email='admin@example.com', password='Sup3r-secret!', full_name='Admin')
        self.client.force_authenticate(admin)
        user = self.make_user()
        response = self.client.patch(self.url('detail', user.pk), {'role_ids': [str(self.admin_role.pk)]}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        body = {'new_password': 'An0ther-pass-word!', 'confirm_password': 'An0ther-pass-word!'}
        self.assertEqual(self.client.post(self.url('set-password', user.pk), body, format='json').status_code, 200)


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
        user = User.objects.create_user(email='staff@example.com', password='Str0ng-pass-word!', full_name='Staff')
        user.roles.add(role)
        return user

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
        holder = User.objects.create_user(email='ops@example.com', password='Str0ng-pass-word!', full_name='Ops')
        holder.roles.add(role)
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
        role = staff.roles.get()
        response = self.client.delete(self.url('detail', role.pk))
        self.assertEqual(response.status_code, 400)
        self.assertIn('still have this role', response.data['message'])
        staff.delete()
        response = self.client.delete(self.url('detail', role.pk))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(Role.objects.filter(pk=role.pk).exists())

    def test_non_superuser_can_read_but_not_change(self):
        staff = self.make_staff()
        self.client.force_authenticate(staff)
        self.assertEqual(self.client.get(self.url('list')).status_code, 200)
        self.assertEqual(self.client.get(self.url('detail', staff.roles.get().pk)).status_code, 200)
        self.assertEqual(self.client.get(self.url('modules')).status_code, 403)
        self.assertEqual(self.client.post(self.url('create'), {'name': 'Mine'}, format='json').status_code, 403)
        self.assertEqual(
            self.client.patch(self.url('detail', staff.roles.get().pk), {'name': 'Mine'}, format='json').status_code, 403
        )
        self.assertEqual(self.client.delete(self.url('detail', staff.roles.get().pk)).status_code, 403)

    def test_modules_and_user_count(self):
        staff = self.make_staff()
        response = self.client.get(self.url('modules'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([module['code'] for module in response.data['data']], list(PERMISSION_LABELS))
        response = self.client.get(self.url('detail', staff.roles.get().pk))
        self.assertEqual(response.data['data']['user_count'], 1)


class MePermissionsTests(APITestCase):
    """GET /auth/me/ lists what the signed-in user's role lets them do, for the sidebar."""

    url = reverse('accounts:apis:auth:me')

    def test_role_user_gets_only_granted_modules(self):
        role = Role.objects.create(name='Staff')
        RolePermission.objects.create(role=role, module='carriers', can_view=True, can_update=True)
        user = User.objects.create_user(email='s@example.com', password='Str0ng-pass-word!', full_name='S')
        user.roles.add(role)
        self.client.force_authenticate(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data['data']['permissions'],
            {'carriers': {'view': True, 'create': False, 'update': True, 'delete': False}},
        )

    def test_superuser_gets_every_module(self):
        admin = User.objects.create_superuser(email='a@example.com', password='Sup3r-secret!', full_name='A')
        self.client.force_authenticate(admin)
        permissions = self.client.get(self.url).data['data']['permissions']
        self.assertEqual(set(permissions), set(PERMISSION_LABELS))

    def test_roles_add_up_and_no_role_means_nothing(self):
        viewer = Role.objects.create(name='Viewer')
        RolePermission.objects.create(role=viewer, module='carriers', can_view=True)
        editor = Role.objects.create(name='Editor')
        RolePermission.objects.create(role=editor, module='carriers', can_view=True, can_update=True)
        RolePermission.objects.create(role=editor, module='agents', can_view=True)
        off = Role.objects.create(name='Off', is_active=False)
        RolePermission.objects.create(role=off, module='users', can_view=True, can_delete=True)
        user = User.objects.create_user(email='s@example.com', password='Str0ng-pass-word!', full_name='S')
        self.client.force_authenticate(user)
        self.assertEqual(self.client.get(self.url).data['data']['permissions'], {})

        user.roles.add(viewer, editor, off)
        # A fresh instance: role_permissions is cached per instance, as it is per request.
        self.client.force_authenticate(User.objects.get(pk=user.pk))
        permissions = self.client.get(self.url).data['data']['permissions']
        self.assertEqual(
            permissions,
            {
                'carriers': {'view': True, 'create': False, 'update': True, 'delete': False},
                'agents': {'view': True, 'create': False, 'update': False, 'delete': False},
            },
        )
