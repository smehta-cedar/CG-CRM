"""Phase 2: the user API, role assignment, and permission enforcement.

Phase 0's model/manager cases live in tests.py.
"""

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.roles.models import Permission, Role

User = get_user_model()


class UserAPITestMixin:
    url = '/api/v1/users/'

    def make_role(self, name, *codenames):
        role = Role.objects.create(name=name)
        role.permissions.set(Permission.objects.filter(codename__in=codenames))
        return role

    def sign_in_with(self, *codenames):
        role = self.make_role('Role ' + ('+'.join(codenames) or 'empty'), *codenames)
        user = User.objects.create_user(
            'actor@example.com', 'pw', full_name='Actor', role=role
        )
        self.client.force_authenticate(user)
        return user


class UserRoleAssignmentTests(UserAPITestMixin, APITestCase):
    """role_id on the way in; role name + codenames on the way out."""

    def setUp(self):
        self.role = self.make_role(
            'Front Desk', 'user.detail', 'user.create', 'role.detail'
        )
        self.root = User.objects.create_superuser(
            'root@example.com', 'pw', full_name='Root'
        )
        self.client.force_authenticate(self.root)

    def test_create_accepts_role_id(self):
        resp = self.client.post(
            self.url,
            {
                'email': 'New@Example.com',
                'full_name': 'New Person',
                'password': 'a-long-enough-passphrase',
                'role_id': self.role.id,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.content)

        body = resp.json()
        self.assertEqual(body['email'], 'new@example.com')
        self.assertEqual(body['role'], {'id': self.role.id, 'name': 'Front Desk'})
        self.assertEqual(
            body['permissions'], ['role.detail', 'user.create', 'user.detail']
        )
        self.assertNotIn('password', body)

        created = User.objects.get(email='new@example.com')
        self.assertEqual(created.role, self.role)
        self.assertTrue(created.check_password('a-long-enough-passphrase'))

    def test_create_without_a_role_is_allowed(self):
        resp = self.client.post(
            self.url,
            {'email': 'norole@example.com', 'full_name': 'No Role',
             'password': 'a-long-enough-passphrase'},
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertIsNone(resp.json()['role'])
        self.assertEqual(resp.json()['permissions'], [])

    def test_create_rejects_a_role_id_that_does_not_exist(self):
        resp = self.client.post(
            self.url,
            {'email': 'bad@example.com', 'full_name': 'Bad',
             'password': 'a-long-enough-passphrase', 'role_id': 9999},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['role_id'], ['No role with id 9999 exists.'])
        self.assertFalse(User.objects.filter(email='bad@example.com').exists())

    def test_create_rejects_a_non_integer_role_id(self):
        resp = self.client.post(
            self.url,
            {'email': 'bad2@example.com', 'full_name': 'Bad',
             'password': 'a-long-enough-passphrase', 'role_id': 'admin'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('role_id', resp.json())

    def test_create_rejects_a_duplicate_email(self):
        resp = self.client.post(
            self.url,
            {'email': 'ROOT@example.com', 'full_name': 'Clash',
             'password': 'a-long-enough-passphrase'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('already exists', resp.json()['email'][0])

    def test_create_rejects_a_weak_password(self):
        resp = self.client.post(
            self.url,
            {'email': 'weak@example.com', 'full_name': 'Weak', 'password': '123'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('password', resp.json())

    def test_create_without_a_password_forces_a_change(self):
        resp = self.client.post(
            self.url,
            {'email': 'pending@example.com', 'full_name': 'Pending'},
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.content)

        created = User.objects.get(email='pending@example.com')
        self.assertFalse(created.has_usable_password())
        self.assertTrue(created.must_change_password)

    def test_update_reassigns_the_role(self):
        target = User.objects.create_user('t@example.com', 'pw', full_name='Target')
        other = self.make_role('Nurse', 'user.detail')

        resp = self.client.patch(
            f'{self.url}{target.id}/', {'role_id': other.id}, format='json'
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['role'], {'id': other.id, 'name': 'Nurse'})
        self.assertEqual(resp.json()['permissions'], ['user.detail'])

        target.refresh_from_db()
        self.assertEqual(target.role, other)

    def test_update_can_clear_the_role(self):
        target = User.objects.create_user(
            't@example.com', 'pw', full_name='Target', role=self.role
        )
        resp = self.client.patch(
            f'{self.url}{target.id}/', {'role_id': None}, format='json'
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIsNone(resp.json()['role'])
        self.assertEqual(resp.json()['permissions'], [])

    def test_update_rejects_a_role_id_that_does_not_exist(self):
        target = User.objects.create_user('t@example.com', 'pw', full_name='Target')
        resp = self.client.patch(
            f'{self.url}{target.id}/', {'role_id': 9999}, format='json'
        )
        self.assertEqual(resp.status_code, 400)
        target.refresh_from_db()
        self.assertIsNone(target.role)

    def test_detail_carries_the_role_name_and_codenames(self):
        target = User.objects.create_user(
            't@example.com', 'pw', full_name='Target', role=self.role
        )
        body = self.client.get(f'{self.url}{target.id}/').json()
        self.assertEqual(body['role']['name'], 'Front Desk')
        self.assertEqual(
            body['permissions'], ['role.detail', 'user.create', 'user.detail']
        )

    def test_is_blocked_cannot_be_set_through_a_general_update(self):
        target = User.objects.create_user('t@example.com', 'pw', full_name='Target')
        resp = self.client.patch(
            f'{self.url}{target.id}/', {'is_blocked': True}, format='json'
        )
        self.assertEqual(resp.status_code, 200)
        target.refresh_from_db()
        self.assertFalse(target.is_blocked)

    def test_update_can_set_a_new_password(self):
        target = User.objects.create_user('t@example.com', 'pw', full_name='Target')
        resp = self.client.patch(
            f'{self.url}{target.id}/',
            {'password': 'another-long-passphrase'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        target.refresh_from_db()
        self.assertTrue(target.check_password('another-long-passphrase'))


class UserPermissionEnforcementTests(UserAPITestMixin, APITestCase):
    def setUp(self):
        self.target = User.objects.create_user(
            'target@example.com', 'pw', full_name='Target'
        )

    def test_no_role_means_no_access(self):
        self.client.force_authenticate(
            User.objects.create_user('plain@example.com', 'pw', full_name='Plain')
        )
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(
            self.client.get(f'{self.url}{self.target.id}/').status_code, 403
        )

    def test_user_detail_grants_read_but_not_write(self):
        self.sign_in_with('user.detail')
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(
            self.client.get(f'{self.url}{self.target.id}/').status_code, 200
        )
        resp = self.client.post(
            self.url,
            {'email': 'x@example.com', 'full_name': 'X',
             'password': 'a-long-enough-passphrase'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_user_create_grants_only_create(self):
        self.sign_in_with('user.create')
        resp = self.client.post(
            self.url,
            {'email': 'x@example.com', 'full_name': 'X',
             'password': 'a-long-enough-passphrase'},
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_user_update_grants_only_update(self):
        self.sign_in_with('user.update')
        resp = self.client.patch(
            f'{self.url}{self.target.id}/', {'full_name': 'Renamed'}, format='json'
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_delete_is_refused(self):
        """Accounts are deactivated, not deleted.

        403 rather than 405: DRF runs permission checks before it dispatches
        the method, and `destroy` is not in `required_permissions`, so the
        fail-closed branch answers first. Fine either way - the account
        survives, and the response does not advertise the routing table.
        """
        self.sign_in_with('user.create', 'user.update', 'user.detail')
        self.assertEqual(
            self.client.delete(f'{self.url}{self.target.id}/').status_code, 403
        )
        self.assertTrue(User.objects.filter(pk=self.target.pk).exists())

    def test_requires_authentication(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)


class SuperuserBypassTests(UserAPITestMixin, APITestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            'root@example.com', 'pw', full_name='Root'
        )

    def test_superuser_holds_every_permission_without_a_role(self):
        self.assertIsNone(self.root.role)
        self.assertTrue(self.root.has_permission('user.create'))
        self.assertTrue(self.root.has_permission('role.delete'))
        self.assertEqual(
            self.root.permission_codenames,
            frozenset(Permission.objects.values_list('codename', flat=True)),
        )

    def test_superuser_bypass_holds_for_an_unknown_codename(self):
        self.assertTrue(self.root.has_permission('something.invented'))

    def test_superuser_permission_list_is_not_empty_in_the_api(self):
        """An empty list would hide every menu from the account that sees all."""
        self.client.force_authenticate(self.root)
        body = self.client.get(f'{self.url}me/').json()

        self.assertIsNone(body['role'])
        self.assertEqual(len(body['permissions']), Permission.objects.count())
        self.assertIn('user.create', body['permissions'])

    def test_superuser_reaches_every_gated_endpoint(self):
        self.client.force_authenticate(self.root)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.get('/api/v1/roles/').status_code, 200)

    def test_a_plain_user_holds_nothing(self):
        plain = User.objects.create_user('p@example.com', 'pw', full_name='P')
        self.assertFalse(plain.has_permission('user.create'))
        self.assertEqual(plain.permission_codenames, frozenset())

    def test_a_role_with_no_permissions_holds_nothing(self):
        parked = self.make_role('Parked')
        user = User.objects.create_user(
            'parked@example.com', 'pw', full_name='Parked', role=parked
        )
        self.assertFalse(user.has_permission('user.detail'))
        self.assertEqual(user.permission_codenames, frozenset())


class MeEndpointTests(UserAPITestMixin, APITestCase):
    def test_any_signed_in_user_may_read_themselves(self):
        """Without this a low-privilege user could not draw their own menu."""
        user = self.sign_in_with('role.detail')
        body = self.client.get(f'{self.url}me/').json()

        self.assertEqual(body['email'], user.email)
        self.assertEqual(body['permissions'], ['role.detail'])
        self.assertEqual(body['role']['name'], 'Role role.detail')

    def test_me_works_for_a_user_who_cannot_list_users(self):
        self.sign_in_with('role.detail')
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.get(f'{self.url}me/').status_code, 200)

    def test_a_user_with_no_role_still_gets_a_response(self):
        self.client.force_authenticate(
            User.objects.create_user('plain@example.com', 'pw', full_name='Plain')
        )
        resp = self.client.get(f'{self.url}me/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()['role'])
        self.assertEqual(resp.json()['permissions'], [])

    def test_requires_authentication(self):
        self.assertEqual(self.client.get(f'{self.url}me/').status_code, 401)
