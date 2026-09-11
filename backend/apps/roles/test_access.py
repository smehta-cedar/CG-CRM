"""Phase 4: the shared decision function, the decorator, and the DRF class.

The point of the design is that all three agree, so a good chunk of this file
asserts exactly that.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework.exceptions import NotAuthenticated
from rest_framework.test import APITestCase

from .models import Permission, Role
from .permissions import (
    ANY_AUTHENTICATED,
    AccessDenied,
    check_access,
    require_permission,
)

User = get_user_model()

PASSWORD = 'a-long-enough-passphrase'


class CheckAccessTests(APITestCase):
    """The five checks, in the order the contract promises."""

    def setUp(self):
        self.role = Role.objects.create(name='Front Desk')
        self.role.permissions.set(
            Permission.objects.filter(codename__in=['user.detail'])
        )
        self.user = User.objects.create_user(
            'user@example.com', PASSWORD, full_name='User', role=self.role
        )

    def assertDenied(self, result, code):
        self.assertFalse(result)
        self.assertEqual(result.code, code)

    # 1. authenticated
    def test_anonymous_is_denied(self):
        self.assertDenied(
            check_access(AnonymousUser(), 'user.detail'), 'not_authenticated'
        )

    def test_none_is_denied(self):
        self.assertDenied(check_access(None, 'user.detail'), 'not_authenticated')

    # 2. not blocked
    def test_blocked_is_denied_even_with_the_permission(self):
        self.user.is_blocked = True
        self.assertDenied(
            check_access(self.user, 'user.detail'), 'account_blocked'
        )

    def test_blocked_beats_the_superuser_bypass(self):
        root = User.objects.create_superuser(
            'root@example.com', PASSWORD, full_name='Root'
        )
        root.is_blocked = True
        self.assertDenied(check_access(root, 'user.detail'), 'account_blocked')

    # 3. no pending password change
    def test_pending_password_change_is_denied(self):
        self.user.must_change_password = True
        self.assertDenied(
            check_access(self.user, 'user.detail'), 'password_change_required'
        )

    def test_pending_password_change_beats_the_superuser_bypass(self):
        """An admin-reset superuser has to change it too."""
        root = User.objects.create_superuser(
            'root@example.com', PASSWORD, full_name='Root'
        )
        root.must_change_password = True
        self.assertDenied(
            check_access(root, 'user.detail'), 'password_change_required'
        )

    def test_the_exemption_lets_a_pending_user_through(self):
        self.user.must_change_password = True
        self.assertTrue(
            check_access(
                self.user, 'user.detail', allow_password_change_pending=True
            )
        )

    def test_the_exemption_does_not_excuse_being_blocked(self):
        self.user.is_blocked = True
        self.user.must_change_password = True
        self.assertDenied(
            check_access(
                self.user, 'user.detail', allow_password_change_pending=True
            ),
            'account_blocked',
        )

    # 4. superuser
    def test_superuser_passes_without_a_role(self):
        root = User.objects.create_superuser(
            'root@example.com', PASSWORD, full_name='Root'
        )
        self.assertIsNone(root.role)
        self.assertTrue(check_access(root, 'user.detail'))
        self.assertTrue(check_access(root, 'anything.invented'))

    # 5. role holds the codename
    def test_granted_codename_passes(self):
        self.assertTrue(check_access(self.user, 'user.detail'))

    def test_ungranted_codename_is_denied(self):
        self.assertDenied(
            check_access(self.user, 'user.create'), 'permission_denied'
        )

    def test_no_role_is_denied(self):
        plain = User.objects.create_user(
            'plain@example.com', PASSWORD, full_name='Plain'
        )
        self.assertDenied(
            check_access(plain, 'user.detail'), 'permission_denied'
        )

    def test_any_authenticated_needs_only_a_session(self):
        plain = User.objects.create_user(
            'plain@example.com', PASSWORD, full_name='Plain'
        )
        self.assertTrue(check_access(plain, ANY_AUTHENTICATED))

    def test_a_none_codename_fails_closed(self):
        self.assertDenied(check_access(self.user, None), 'permission_denied')

    def test_result_is_falsy_when_denied_and_truthy_when_allowed(self):
        self.assertTrue(bool(check_access(self.user, 'user.detail')))
        self.assertFalse(bool(check_access(self.user, 'user.create')))

    def test_raise_for_result_maps_codes_to_exceptions(self):
        check_access(self.user, 'user.detail').raise_for_result()  # no raise

        with self.assertRaises(NotAuthenticated):
            check_access(AnonymousUser(), 'user.detail').raise_for_result()

        with self.assertRaises(AccessDenied) as caught:
            check_access(self.user, 'user.create').raise_for_result()
        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(caught.exception.detail['code'], 'permission_denied')


class RequirePermissionDecoratorTests(APITestCase):
    """The decorator form, and that it agrees with the function."""

    def setUp(self):
        self.role = Role.objects.create(name='Front Desk')
        self.role.permissions.set(
            Permission.objects.filter(codename__in=['user.detail'])
        )
        self.user = User.objects.create_user(
            'user@example.com', PASSWORD, full_name='User', role=self.role
        )

    def fake_request(self, user):
        return type('Req', (), {'user': user, 'method': 'GET'})()

    def make_view(self, codename, **kwargs):
        @require_permission(codename, **kwargs)
        def view(self, request):
            return 'ran'

        return view

    def test_allows_when_granted(self):
        view = self.make_view('user.detail')
        self.assertEqual(view(None, self.fake_request(self.user)), 'ran')

    def test_denies_when_not_granted(self):
        view = self.make_view('user.create')
        with self.assertRaises(AccessDenied) as caught:
            view(None, self.fake_request(self.user))
        self.assertEqual(caught.exception.detail['code'], 'permission_denied')

    def test_denies_anonymous(self):
        view = self.make_view('user.detail')
        with self.assertRaises(NotAuthenticated):
            view(None, self.fake_request(AnonymousUser()))

    def test_honours_the_password_change_gate(self):
        self.user.must_change_password = True
        view = self.make_view('user.detail')
        with self.assertRaises(AccessDenied) as caught:
            view(None, self.fake_request(self.user))
        self.assertEqual(
            caught.exception.detail['code'], 'password_change_required'
        )

    def test_honours_the_exemption(self):
        self.user.must_change_password = True
        view = self.make_view('user.detail', allow_password_change_pending=True)
        self.assertEqual(view(None, self.fake_request(self.user)), 'ran')

    def test_works_on_a_function_based_view_with_no_self(self):
        @require_permission('user.detail')
        def view(request):
            return 'ran'

        self.assertEqual(view(self.fake_request(self.user)), 'ran')

    def test_preserves_the_wrapped_name_and_docstring(self):
        @require_permission('user.detail')
        def my_view(self, request):
            """Original docstring."""

        self.assertEqual(my_view.__name__, 'my_view')
        self.assertEqual(my_view.__doc__, 'Original docstring.')
        self.assertEqual(my_view.required_permission, 'user.detail')

    def test_raises_typeerror_without_a_request(self):
        view = self.make_view('user.detail')
        with self.assertRaises(TypeError):
            view('not a request')

    def test_decorator_and_function_agree(self):
        """The whole point of keeping the logic in one function."""
        cases = [
            (self.user, 'user.detail'),
            (self.user, 'user.create'),
            (self.user, ANY_AUTHENTICATED),
            (User.objects.create_superuser(
                'root@example.com', PASSWORD, full_name='Root'), 'user.create'),
            (User.objects.create_user(
                'plain@example.com', PASSWORD, full_name='Plain'), 'user.detail'),
        ]
        for user, codename in cases:
            with self.subTest(user=user.email, codename=codename):
                expected = bool(check_access(user, codename))
                view = self.make_view(codename)
                try:
                    view(None, self.fake_request(user))
                    actual = True
                except (AccessDenied, NotAuthenticated):
                    actual = False
                self.assertEqual(actual, expected)


class PasswordChangeGateEndToEndTests(APITestCase):
    """The forced change now bites over HTTP - and does not deadlock."""

    login_url = '/api/v1/auth/login/'
    change_url = '/api/v1/auth/change-password/'

    def setUp(self):
        role = Role.objects.create(name='Front Desk')
        role.permissions.set(
            Permission.objects.filter(codename__in=['user.detail', 'role.detail'])
        )
        self.user = User.objects.create_user(
            'user@example.com', PASSWORD, full_name='User', role=role,
            must_change_password=True,
        )
        tokens = self.client.post(
            self.login_url,
            {'email': 'user@example.com', 'password': PASSWORD},
            format='json',
        ).json()
        self.assertTrue(tokens['must_change_password'])
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    def test_ordinary_endpoints_are_refused_with_a_catchable_code(self):
        for url in ('/api/v1/users/', '/api/v1/roles/', '/api/v1/permissions/'):
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 403)
                self.assertEqual(
                    resp.json()['code'], 'password_change_required'
                )

    def test_the_change_password_endpoint_stays_reachable(self):
        """Gate it on the flag and the user can never clear the flag."""
        resp = self.client.post(
            self.change_url,
            {'old_password': PASSWORD, 'new_password': 'a-different-passphrase'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_me_stays_reachable(self):
        resp = self.client.get('/api/v1/users/me/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['must_change_password'])

    def test_everything_opens_up_once_the_password_is_changed(self):
        body = self.client.post(
            self.change_url,
            {'old_password': PASSWORD, 'new_password': 'a-different-passphrase'},
            format='json',
        ).json()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {body['access']}")

        self.assertEqual(self.client.get('/api/v1/roles/').status_code, 200)
        self.assertEqual(self.client.get('/api/v1/users/').status_code, 200)

    def test_a_superuser_is_held_to_the_same_rule(self):
        root = User.objects.create_superuser(
            'root@example.com', PASSWORD, full_name='Root',
            must_change_password=True,
        )
        tokens = self.client.post(
            self.login_url,
            {'email': 'root@example.com', 'password': PASSWORD},
            format='json',
        ).json()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        resp = self.client.get('/api/v1/roles/')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()['code'], 'password_change_required')
        self.assertTrue(root.is_superuser)
