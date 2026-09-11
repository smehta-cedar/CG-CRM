from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from rest_framework.exceptions import NotAuthenticated
from rest_framework.test import APITestCase

from .catalog import PERMISSIONS, codename_for
from .models import Permission, Role
from .permissions import ANY_AUTHENTICATED, AccessDenied, HasRolePermission
from .serializers import RoleDeleteSerializer

User = get_user_model()


class CatalogTests(APITestCase):
    def test_catalog_matches_the_database(self):
        """Guards against catalog.py gaining an entry with no data migration."""
        expected = {codename_for(r, a) for _, r, a in PERMISSIONS}
        actual = set(Permission.objects.values_list('codename', flat=True))
        self.assertEqual(actual, expected)

    def test_the_ten_catalog_codenames(self):
        self.assertEqual(
            sorted(Permission.objects.values_list('codename', flat=True)),
            [
                'role.create', 'role.delete', 'role.detail', 'role.update',
                'user.block', 'user.change_password', 'user.create',
                'user.detail', 'user.unblock', 'user.update',
            ],
        )

    def test_codename_is_unique(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Permission.objects.create(
                module='X', resource='Other', action='thing', codename='user.create'
            )

    def test_resource_action_pair_is_unique(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Permission.objects.create(
                module='X', resource='User', action='create', codename='other.code'
            )

    def test_label_humanises_the_action(self):
        perm = Permission.objects.get(codename='user.change_password')
        self.assertEqual(perm.label, 'Change Password')

    def test_seed_command_is_idempotent(self):
        before = Permission.objects.count()
        out = StringIO()
        call_command('seed_permissions', stdout=out)
        self.assertEqual(Permission.objects.count(), before)
        self.assertIn('0 created, 0 updated, 0 stale', out.getvalue())

    def test_seed_command_reports_then_prunes_stale_rows(self):
        Permission.objects.create(
            module='Gone', resource='Ghost', action='haunt', codename='ghost.haunt'
        )
        out = StringIO()
        call_command('seed_permissions', stdout=out)
        self.assertIn('ghost.haunt', out.getvalue())
        self.assertTrue(Permission.objects.filter(codename='ghost.haunt').exists())

        call_command('seed_permissions', '--prune', stdout=StringIO())
        self.assertFalse(Permission.objects.filter(codename='ghost.haunt').exists())

    def test_seed_command_refiles_a_moved_permission(self):
        perm = Permission.objects.get(codename='user.create')
        Permission.objects.filter(pk=perm.pk).update(module='Wrong Module')

        out = StringIO()
        call_command('seed_permissions', stdout=out)
        perm.refresh_from_db()
        self.assertEqual(perm.module, 'User Management')
        self.assertIn('1 updated', out.getvalue())

    def test_role_has_perm(self):
        role = Role.objects.create(name='Checker')
        role.permissions.add(Permission.objects.get(codename='user.create'))
        self.assertTrue(role.has_perm('user.create'))
        self.assertFalse(role.has_perm('user.block'))


class AuthenticatedAPITestCase(APITestCase):
    """Drives the endpoints as a superuser.

    These cases are about the endpoints' behaviour, not about who may reach
    them; RolePermissionEnforcementTests covers the gate itself.
    """

    def setUp(self):
        self.user = User.objects.create_superuser(
            'caller@example.com', 'pw', full_name='API Caller'
        )
        self.client.force_authenticate(self.user)


class PermissionTreeTests(AuthenticatedAPITestCase):
    url = '/api/v1/permissions/'

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_returns_the_grouped_tree(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

        modules = resp.json()['modules']
        self.assertEqual(
            [m['module'] for m in modules], ['Role Management', 'User Management']
        )

        user_module = next(m for m in modules if m['module'] == 'User Management')
        self.assertEqual([r['resource'] for r in user_module['resources']], ['User'])

        actions = user_module['resources'][0]['actions']
        self.assertEqual(
            [a['action'] for a in actions],
            ['create', 'update', 'detail', 'block', 'unblock', 'change_password'],
        )
        self.assertEqual(
            actions[0],
            {
                'id': Permission.objects.get(codename='user.create').id,
                'action': 'create',
                'codename': 'user.create',
                'label': 'Create',
            },
        )

    def test_every_catalog_entry_appears_exactly_once(self):
        modules = self.client.get(self.url).json()['modules']
        codenames = [
            a['codename']
            for m in modules for r in m['resources'] for a in r['actions']
        ]
        self.assertEqual(len(codenames), len(PERMISSIONS))
        self.assertEqual(len(set(codenames)), len(PERMISSIONS))


class RoleAPITests(AuthenticatedAPITestCase):
    url = '/api/v1/roles/'

    def setUp(self):
        super().setUp()
        self.perms = list(Permission.objects.filter(resource='Role'))

    def create_role(self, name='Manager', permission_ids=None):
        payload = {'name': name}
        payload['permission_ids'] = (
            [p.id for p in self.perms] if permission_ids is None else permission_ids
        )
        return self.client.post(self.url, payload, format='json')

    # --- create -----------------------------------------------------------
    def test_create(self):
        resp = self.create_role()
        self.assertEqual(resp.status_code, 201, resp.content)

        body = resp.json()
        self.assertEqual(body['name'], 'Manager')
        self.assertEqual(body['user_count'], 0)
        self.assertEqual(
            sorted(p['codename'] for p in body['permissions']),
            ['role.create', 'role.delete', 'role.detail', 'role.update'],
        )

    def test_create_without_permissions_is_allowed(self):
        resp = self.client.post(self.url, {'name': 'Parked'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()['permissions'], [])

    def test_create_rejects_a_duplicate_name_case_insensitively(self):
        self.create_role(name='Manager')
        resp = self.create_role(name='  manager  ')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('already exists', resp.json()['name'][0])

    def test_create_strips_surrounding_whitespace(self):
        resp = self.create_role(name='  Nurse  ')
        self.assertEqual(resp.json()['name'], 'Nurse')

    def test_create_rejects_an_unknown_permission_id(self):
        resp = self.create_role(permission_ids=[9999])
        self.assertEqual(resp.status_code, 400)
        self.assertIn('permission_ids', resp.json())

    # --- list / detail ----------------------------------------------------
    def test_list_and_detail(self):
        role = Role.objects.create(name='Viewer')
        role.permissions.set(self.perms[:1])

        listing = self.client.get(self.url)
        self.assertEqual(listing.status_code, 200)
        # No global pagination is configured, so this is a plain list.
        self.assertEqual([r['name'] for r in listing.json()], ['Viewer'])

        detail = self.client.get(f'{self.url}{role.id}/')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()['name'], 'Viewer')
        self.assertEqual(len(detail.json()['permissions']), 1)

    def test_list_reports_user_count(self):
        role = Role.objects.create(name='Staffed')
        User.objects.create_user('a@example.com', 'pw', full_name='A', role=role)
        User.objects.create_user('b@example.com', 'pw', full_name='B', role=role)

        self.assertEqual(self.client.get(f'{self.url}{role.id}/').json()['user_count'], 2)

    # --- update -----------------------------------------------------------
    def test_update_replaces_the_permission_set(self):
        role_id = self.create_role().json()['id']
        keep = Permission.objects.get(codename='role.detail')

        resp = self.client.patch(
            f'{self.url}{role_id}/',
            {'name': 'Read Only', 'permission_ids': [keep.id]},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['name'], 'Read Only')
        self.assertEqual(
            [p['codename'] for p in resp.json()['permissions']], ['role.detail']
        )

    def test_update_may_keep_its_own_name(self):
        role_id = self.create_role(name='Manager').json()['id']
        resp = self.client.patch(
            f'{self.url}{role_id}/', {'name': 'Manager'}, format='json'
        )
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_update_rejects_another_roles_name(self):
        self.create_role(name='Manager')
        other_id = self.create_role(name='Nurse').json()['id']
        resp = self.client.patch(
            f'{self.url}{other_id}/', {'name': 'manager'}, format='json'
        )
        self.assertEqual(resp.status_code, 400)

    # --- delete -----------------------------------------------------------
    def test_delete_an_unassigned_role(self):
        role = Role.objects.create(name='Unused')
        resp = self.client.delete(f'{self.url}{role.id}/')
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Role.objects.filter(pk=role.pk).exists())

    def test_delete_is_blocked_while_users_hold_the_role(self):
        role = Role.objects.create(name='Staffed')
        for i in range(3):
            User.objects.create_user(
                f'u{i}@example.com', 'pw', full_name=f'User {i}', role=role
            )

        resp = self.client.delete(f'{self.url}{role.id}/')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['detail'], ['This role is assigned to 3 users.'])
        self.assertTrue(Role.objects.filter(pk=role.pk).exists())

    def test_delete_message_is_singular_for_one_user(self):
        role = Role.objects.create(name='Solo')
        User.objects.create_user('solo@example.com', 'pw', full_name='Solo', role=role)

        resp = self.client.delete(f'{self.url}{role.id}/')
        self.assertEqual(resp.json()['detail'], ['This role is assigned to 1 user.'])

    def test_delete_succeeds_once_the_role_is_vacated(self):
        role = Role.objects.create(name='Temp')
        user = User.objects.create_user(
            'temp@example.com', 'pw', full_name='Temp', role=role
        )
        self.assertEqual(self.client.delete(f'{self.url}{role.id}/').status_code, 400)

        user.role = None
        user.save(update_fields=['role'])
        self.assertEqual(self.client.delete(f'{self.url}{role.id}/').status_code, 204)

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(
            self.client.post(self.url, {'name': 'X'}, format='json').status_code, 401
        )


class RoleDeleteGuardTests(APITestCase):
    """The guard is a serializer so callers that are not the viewset agree."""

    def test_serializer_can_be_used_directly(self):
        role = Role.objects.create(name='Direct')
        self.assertTrue(RoleDeleteSerializer.for_role(role).is_valid())

        User.objects.create_user('d@example.com', 'pw', full_name='D', role=role)
        serializer = RoleDeleteSerializer.for_role(role)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            serializer.errors['detail'][0], 'This role is assigned to 1 user.'
        )

    def test_database_refuses_the_delete_even_without_the_serializer(self):
        """PROTECT is the backstop for callers that skip the serializer."""
        role = Role.objects.create(name='Protected')
        User.objects.create_user('p@example.com', 'pw', full_name='P', role=role)

        with self.assertRaises(ProtectedError):
            role.delete()

    def test_a_refused_delete_leaves_the_user_attached(self):
        role = Role.objects.create(name='Held')
        user = User.objects.create_user('h@example.com', 'pw', full_name='H', role=role)

        with self.assertRaises(ProtectedError), transaction.atomic():
            role.delete()

        user.refresh_from_db()
        self.assertEqual(user.role, role)


class RolePermissionEnforcementTests(APITestCase):
    """The role endpoints are gated on the catalog, not just on being signed in."""

    def setUp(self):
        self.role = Role.objects.create(name='Target')
        self.plain = User.objects.create_user(
            'plain@example.com', 'pw', full_name='No Role'
        )

    def as_user_with(self, *codenames):
        role = Role.objects.create(name='Granted ' + ','.join(codenames or ['none']))
        role.permissions.set(Permission.objects.filter(codename__in=codenames))
        user = User.objects.create_user(
            f'{len(codenames)}granted@example.com', 'pw', full_name='Granted',
            role=role,
        )
        self.client.force_authenticate(user)
        return user

    def test_no_role_means_no_access(self):
        self.client.force_authenticate(self.plain)
        self.assertEqual(self.client.get('/api/v1/roles/').status_code, 403)
        self.assertEqual(
            self.client.post('/api/v1/roles/', {'name': 'X'}, format='json').status_code,
            403,
        )
        self.assertEqual(
            self.client.delete(f'/api/v1/roles/{self.role.id}/').status_code, 403
        )

    def test_role_detail_grants_read_but_not_write(self):
        self.as_user_with('role.detail')
        self.assertEqual(self.client.get('/api/v1/roles/').status_code, 200)
        self.assertEqual(
            self.client.get(f'/api/v1/roles/{self.role.id}/').status_code, 200
        )
        self.assertEqual(
            self.client.post('/api/v1/roles/', {'name': 'X'}, format='json').status_code,
            403,
        )
        self.assertEqual(
            self.client.delete(f'/api/v1/roles/{self.role.id}/').status_code, 403
        )

    def test_role_create_grants_only_create(self):
        self.as_user_with('role.create')
        self.assertEqual(
            self.client.post('/api/v1/roles/', {'name': 'X'}, format='json').status_code,
            201,
        )
        self.assertEqual(self.client.get('/api/v1/roles/').status_code, 403)

    def test_role_delete_grants_only_delete(self):
        self.as_user_with('role.delete')
        self.assertEqual(
            self.client.delete(f'/api/v1/roles/{self.role.id}/').status_code, 204
        )

    def test_role_update_grants_only_update(self):
        self.as_user_with('role.update')
        resp = self.client.patch(
            f'/api/v1/roles/{self.role.id}/', {'name': 'Renamed'}, format='json'
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(
            self.client.post('/api/v1/roles/', {'name': 'X'}, format='json').status_code,
            403,
        )

    def test_superuser_bypasses_roles_entirely(self):
        root = User.objects.create_superuser(
            'root@example.com', 'pw', full_name='Root'
        )
        self.assertIsNone(root.role)
        self.client.force_authenticate(root)

        self.assertEqual(self.client.get('/api/v1/roles/').status_code, 200)
        self.assertEqual(
            self.client.post('/api/v1/roles/', {'name': 'X'}, format='json').status_code,
            201,
        )
        self.assertEqual(
            self.client.delete(f'/api/v1/roles/{self.role.id}/').status_code, 204
        )

    def test_permission_tree_is_open_to_any_signed_in_user(self):
        """The role editor needs the catalog before it can tick any boxes."""
        self.client.force_authenticate(self.plain)
        self.assertEqual(self.client.get('/api/v1/permissions/').status_code, 200)


class HasRolePermissionUnitTests(APITestCase):
    """The permission class itself, away from any particular view."""

    class FakeView:
        def __init__(self, action, required=None, exempt=()):
            self.action = action
            self.password_change_exempt_actions = exempt
            if required is not None:
                self.required_permissions = required

    def check(self, user, view):
        request = type('Req', (), {'user': user, 'method': 'GET'})()
        return HasRolePermission().has_permission(request, view)

    def assertDenied(self, user, view, code):
        with self.assertRaises(AccessDenied) as caught:
            self.check(user, view)
        self.assertEqual(caught.exception.detail['code'], code)

    def setUp(self):
        self.role = Role.objects.create(name='Partial')
        self.role.permissions.set(
            Permission.objects.filter(codename__in=['user.detail'])
        )
        self.user = User.objects.create_user(
            'partial@example.com', 'pw', full_name='Partial', role=self.role
        )

    def test_granted_action_allowed(self):
        self.assertTrue(
            self.check(self.user, self.FakeView('retrieve', {'retrieve': 'user.detail'}))
        )

    def test_ungranted_action_denied(self):
        self.assertDenied(
            self.user, self.FakeView('create', {'create': 'user.create'}),
            'permission_denied',
        )

    def test_unmapped_action_fails_closed(self):
        """An action missing from the map is denied, not waved through."""
        self.assertDenied(
            self.user, self.FakeView('export', {'retrieve': 'user.detail'}),
            'permission_denied',
        )

    def test_view_without_a_map_is_not_gated(self):
        self.assertTrue(self.check(self.user, self.FakeView('retrieve')))

    def test_any_authenticated_sentinel_allows(self):
        self.assertTrue(
            self.check(self.user, self.FakeView('tree', {'tree': ANY_AUTHENTICATED}))
        )

    def test_anonymous_is_denied_even_when_open(self):
        from django.contrib.auth.models import AnonymousUser

        view = self.FakeView('tree', {'tree': ANY_AUTHENTICATED})
        with self.assertRaises(NotAuthenticated):
            self.check(AnonymousUser(), view)

    def test_pending_password_change_blocks_a_granted_action(self):
        self.user.must_change_password = True
        self.user.save(update_fields=['must_change_password'])
        self.assertDenied(
            self.user, self.FakeView('retrieve', {'retrieve': 'user.detail'}),
            'password_change_required',
        )

    def test_an_exempt_action_survives_a_pending_password_change(self):
        self.user.must_change_password = True
        self.user.save(update_fields=['must_change_password'])
        view = self.FakeView(
            'me', {'me': ANY_AUTHENTICATED}, exempt={'me'}
        )
        self.assertTrue(self.check(self.user, view))
