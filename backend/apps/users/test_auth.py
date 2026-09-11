"""Phase 3: login, password changes, blocking, and token invalidation."""

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from apps.roles.models import Permission, Role

from .models import LoginType
from .tokens import TOKEN_VERSION_CLAIM, tokens_for_user

User = get_user_model()

PASSWORD = 'a-long-enough-passphrase'
NEW_PASSWORD = 'a-different-long-passphrase'


class AuthTestMixin:
    login_url = '/api/v1/auth/login/'
    change_url = '/api/v1/auth/change-password/'
    users_url = '/api/v1/users/'

    def make_user(self, email='user@example.com', password=PASSWORD, **kwargs):
        return User.objects.create_user(
            email, password, full_name=kwargs.pop('full_name', 'Test User'), **kwargs
        )

    def make_admin(self, *codenames, email='admin@example.com'):
        role = Role.objects.create(name='Admin ' + ('+'.join(codenames) or 'none'))
        role.permissions.set(Permission.objects.filter(codename__in=codenames))
        return self.make_user(email=email, full_name='Admin', role=role)

    def login(self, email='user@example.com', password=PASSWORD):
        return self.client.post(
            self.login_url, {'email': email, 'password': password}, format='json'
        )

    def bearer(self, access):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')


class LoginTests(AuthTestMixin, APITestCase):
    def setUp(self):
        self.user = self.make_user()

    def test_successful_login_returns_a_token_pair(self):
        resp = self.login()
        self.assertEqual(resp.status_code, 200, resp.content)

        body = resp.json()
        self.assertIn('access', body)
        self.assertIn('refresh', body)
        self.assertEqual(body['must_change_password'], False)
        self.assertEqual(body['user']['email'], 'user@example.com')

    def test_login_is_case_insensitive_on_email(self):
        self.assertEqual(self.login(email='USER@Example.com').status_code, 200)

    def test_login_reports_must_change_password(self):
        self.user.must_change_password = True
        self.user.save(update_fields=['must_change_password'])
        self.assertTrue(self.login().json()['must_change_password'])

    def test_login_response_carries_role_and_permissions(self):
        role = Role.objects.create(name='Front Desk')
        role.permissions.set(Permission.objects.filter(codename='user.detail'))
        self.user.role = role
        self.user.save(update_fields=['role'])

        body = self.login().json()
        self.assertEqual(body['user']['role']['name'], 'Front Desk')
        self.assertEqual(body['user']['permissions'], ['user.detail'])

    # --- the three distinct failures --------------------------------------
    def test_wrong_password_is_invalid_credentials(self):
        resp = self.login(password='wrong-password')
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()['code'], 'invalid_credentials')

    def test_unknown_email_is_invalid_credentials(self):
        resp = self.login(email='nobody@example.com')
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()['code'], 'invalid_credentials')

    def test_blocked_user_gets_a_distinct_code(self):
        self.user.is_blocked = True
        self.user.save(update_fields=['is_blocked'])

        resp = self.login()
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()['code'], 'account_blocked')
        self.assertIn('blocked', resp.json()['detail'])

    def test_inactive_user_gets_a_distinct_code(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])

        resp = self.login()
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()['code'], 'account_inactive')
        self.assertIn('inactive', resp.json()['detail'])

    def test_status_reasons_are_withheld_until_the_password_is_proven(self):
        """Otherwise the endpoint is an account-enumeration oracle.

        A blocked account with the wrong password must be indistinguishable
        from an address that has no account at all.
        """
        self.user.is_blocked = True
        self.user.save(update_fields=['is_blocked'])

        blocked_wrong_pw = self.login(password='wrong-password').json()
        no_such_account = self.login(email='nobody@example.com').json()
        self.assertEqual(blocked_wrong_pw, no_such_account)

    def test_login_needs_no_authentication(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer nonsense')
        self.assertEqual(self.login().status_code, 200)

    def test_missing_fields_are_a_400(self):
        resp = self.client.post(self.login_url, {'email': 'user@example.com'},
                                format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('password', resp.json())


class TokenVersionTests(AuthTestMixin, APITestCase):
    def setUp(self):
        self.user = self.make_user()

    def test_issued_tokens_carry_the_version_claim(self):
        from rest_framework_simplejwt.tokens import AccessToken

        pair = tokens_for_user(self.user)
        self.assertEqual(AccessToken(pair['access'])[TOKEN_VERSION_CLAIM], 0)

    def test_a_valid_token_authenticates(self):
        self.bearer(self.login().json()['access'])
        self.assertEqual(self.client.get(f'{self.users_url}me/').status_code, 200)

    def test_bumping_the_version_kills_an_outstanding_access_token(self):
        self.bearer(self.login().json()['access'])
        self.assertEqual(self.client.get(f'{self.users_url}me/').status_code, 200)

        self.user.invalidate_tokens()
        self.assertEqual(self.client.get(f'{self.users_url}me/').status_code, 401)

    def test_invalidate_tokens_increments_by_one(self):
        self.assertEqual(self.user.token_version, 0)
        self.user.invalidate_tokens()
        self.assertEqual(self.user.token_version, 1)
        self.user.invalidate_tokens()
        self.assertEqual(self.user.token_version, 2)

    def test_refresh_preserves_the_version_stamp(self):
        """A refreshed access token must stay invalidatable."""
        refresh = self.login().json()['refresh']
        resp = self.client.post(
            '/api/v1/auth/token/refresh/', {'refresh': refresh}, format='json'
        )
        self.assertEqual(resp.status_code, 200, resp.content)

        refreshed_access = resp.json()['access']
        self.bearer(refreshed_access)
        self.assertEqual(self.client.get(f'{self.users_url}me/').status_code, 200)

        self.user.invalidate_tokens()
        self.assertEqual(self.client.get(f'{self.users_url}me/').status_code, 401)

    def test_a_token_with_no_version_claim_is_rejected(self):
        """Tokens minted before this mechanism existed must not keep working."""
        from rest_framework_simplejwt.tokens import RefreshToken

        bare = RefreshToken.for_user(self.user)
        self.bearer(str(bare.access_token))
        self.assertEqual(self.client.get(f'{self.users_url}me/').status_code, 401)

    def test_blocking_rejects_an_access_token_even_at_the_same_version(self):
        access = self.login().json()['access']
        User.objects.filter(pk=self.user.pk).update(is_blocked=True)

        self.bearer(access)
        self.assertEqual(self.client.get(f'{self.users_url}me/').status_code, 401)


class ChangeOwnPasswordTests(AuthTestMixin, APITestCase):
    def setUp(self):
        self.user = self.make_user(must_change_password=True)
        self.bearer(self.login().json()['access'])

    def test_changes_the_password_and_clears_the_flag(self):
        resp = self.client.post(
            self.change_url,
            {'old_password': PASSWORD, 'new_password': NEW_PASSWORD},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        self.assertFalse(self.user.must_change_password)

    def test_returns_a_working_token_pair(self):
        """The change invalidates the caller's own tokens; it must hand back new ones."""
        body = self.client.post(
            self.change_url,
            {'old_password': PASSWORD, 'new_password': NEW_PASSWORD},
            format='json',
        ).json()

        self.assertIn('access', body)
        self.bearer(body['access'])
        self.assertEqual(self.client.get(f'{self.users_url}me/').status_code, 200)

    def test_other_sessions_are_ended(self):
        other_session_access = self.login().json()['access']

        self.client.post(
            self.change_url,
            {'old_password': PASSWORD, 'new_password': NEW_PASSWORD},
            format='json',
        )

        self.bearer(other_session_access)
        self.assertEqual(self.client.get(f'{self.users_url}me/').status_code, 401)

    def test_wrong_old_password_is_rejected(self):
        resp = self.client.post(
            self.change_url,
            {'old_password': 'not-my-password', 'new_password': NEW_PASSWORD},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('old_password', resp.json())

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))

    def test_new_password_must_differ(self):
        resp = self.client.post(
            self.change_url,
            {'old_password': PASSWORD, 'new_password': PASSWORD},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('new_password', resp.json())

    def test_weak_new_password_is_rejected(self):
        resp = self.client.post(
            self.change_url,
            {'old_password': PASSWORD, 'new_password': '123'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('new_password', resp.json())

    def test_requires_authentication(self):
        self.client.credentials()
        resp = self.client.post(
            self.change_url,
            {'old_password': PASSWORD, 'new_password': NEW_PASSWORD},
            format='json',
        )
        self.assertEqual(resp.status_code, 401)

    def test_reachable_while_must_change_password_is_set(self):
        """The flag must not lock a user out of the endpoint that clears it."""
        self.assertTrue(self.user.must_change_password)
        resp = self.client.post(
            self.change_url,
            {'old_password': PASSWORD, 'new_password': NEW_PASSWORD},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)


class AdminSetPasswordTests(AuthTestMixin, APITestCase):
    def setUp(self):
        self.admin = self.make_admin('user.change_password')
        self.target = self.make_user(email='target@example.com')
        self.client.force_authenticate(self.admin)

    def url_for(self, user):
        return f'{self.users_url}{user.id}/change-password/'

    def test_sets_the_password_and_forces_a_change(self):
        resp = self.client.post(
            self.url_for(self.target), {'new_password': NEW_PASSWORD}, format='json'
        )
        self.assertEqual(resp.status_code, 200, resp.content)

        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password(NEW_PASSWORD))
        self.assertTrue(self.target.must_change_password)

    def test_needs_no_old_password(self):
        resp = self.client.post(
            self.url_for(self.target), {'new_password': NEW_PASSWORD}, format='json'
        )
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_ends_the_targets_sessions(self):
        self.client.force_authenticate(None)
        target_access = self.login(email='target@example.com').json()['access']

        self.client.force_authenticate(self.admin)
        self.client.post(
            self.url_for(self.target), {'new_password': NEW_PASSWORD}, format='json'
        )

        self.client.force_authenticate(None)
        self.bearer(target_access)
        self.assertEqual(self.client.get(f'{self.users_url}me/').status_code, 401)

    def test_the_target_can_then_sign_in_and_is_told_to_change(self):
        self.client.post(
            self.url_for(self.target), {'new_password': NEW_PASSWORD}, format='json'
        )
        self.client.force_authenticate(None)

        body = self.login(email='target@example.com', password=NEW_PASSWORD).json()
        self.assertTrue(body['must_change_password'])

    def test_weak_password_is_rejected(self):
        resp = self.client.post(
            self.url_for(self.target), {'new_password': '123'}, format='json'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('new_password', resp.json())

    def test_cannot_be_aimed_at_yourself(self):
        resp = self.client.post(
            self.url_for(self.admin), {'new_password': NEW_PASSWORD}, format='json'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('auth/change-password', resp.json()['detail'][0])

    def test_requires_the_change_password_permission(self):
        self.client.force_authenticate(self.make_admin(email='nobody@example.com'))
        resp = self.client.post(
            self.url_for(self.target), {'new_password': NEW_PASSWORD}, format='json'
        )
        self.assertEqual(resp.status_code, 403)


class BlockUnblockTests(AuthTestMixin, APITestCase):
    def setUp(self):
        self.admin = self.make_admin('user.block', 'user.unblock', 'user.detail')
        self.target = self.make_user(email='target@example.com')
        self.client.force_authenticate(self.admin)

    def block_url(self, user):
        return f'{self.users_url}{user.id}/block/'

    def unblock_url(self, user):
        return f'{self.users_url}{user.id}/unblock/'

    def test_block_sets_the_flag(self):
        resp = self.client.post(self.block_url(self.target))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json()['is_blocked'])

        self.target.refresh_from_db()
        self.assertTrue(self.target.is_blocked)

    def test_block_invalidates_existing_access_tokens(self):
        self.client.force_authenticate(None)
        target_access = self.login(email='target@example.com').json()['access']

        self.bearer(target_access)
        self.assertEqual(self.client.get(f'{self.users_url}me/').status_code, 200)

        self.client.credentials()
        self.client.force_authenticate(self.admin)
        self.client.post(self.block_url(self.target))

        self.client.force_authenticate(None)
        self.bearer(target_access)
        self.assertEqual(self.client.get(f'{self.users_url}me/').status_code, 401)

    def test_block_blacklists_outstanding_refresh_tokens(self):
        self.client.force_authenticate(None)
        target_refresh = self.login(email='target@example.com').json()['refresh']

        self.client.force_authenticate(self.admin)
        self.client.post(self.block_url(self.target))

        self.assertTrue(
            BlacklistedToken.objects.filter(token__user=self.target).exists()
        )

        self.client.force_authenticate(None)
        resp = self.client.post(
            '/api/v1/auth/token/refresh/', {'refresh': target_refresh}, format='json'
        )
        self.assertEqual(resp.status_code, 401)

    def test_a_blocked_user_cannot_log_back_in(self):
        self.client.post(self.block_url(self.target))
        self.client.force_authenticate(None)

        resp = self.login(email='target@example.com')
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()['code'], 'account_blocked')

    def test_unblock_restores_sign_in(self):
        self.client.post(self.block_url(self.target))
        resp = self.client.post(self.unblock_url(self.target))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(resp.json()['is_blocked'])

        self.client.force_authenticate(None)
        self.assertEqual(self.login(email='target@example.com').status_code, 200)

    def test_unblock_does_not_revive_the_old_tokens(self):
        self.client.force_authenticate(None)
        old_access = self.login(email='target@example.com').json()['access']

        self.client.force_authenticate(self.admin)
        self.client.post(self.block_url(self.target))
        self.client.post(self.unblock_url(self.target))

        self.client.force_authenticate(None)
        self.bearer(old_access)
        self.assertEqual(self.client.get(f'{self.users_url}me/').status_code, 401)

    def test_cannot_block_yourself(self):
        resp = self.client.post(self.block_url(self.admin))
        self.assertEqual(resp.status_code, 400)
        self.assertIn('your own account', resp.json()['detail'][0])

        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_blocked)

    def test_block_requires_the_block_permission(self):
        self.client.force_authenticate(self.make_admin(email='nobody@example.com'))
        self.assertEqual(self.client.post(self.block_url(self.target)).status_code, 403)

    def test_unblock_requires_the_unblock_permission(self):
        self.client.force_authenticate(
            self.make_admin('user.block', email='blockonly@example.com')
        )
        self.assertEqual(self.client.post(self.block_url(self.target)).status_code, 200)
        self.assertEqual(
            self.client.post(self.unblock_url(self.target)).status_code, 403
        )


class SsoAccountTests(AuthTestMixin, APITestCase):
    """login_type is an auth-provider field; SSO accounts hold no local password."""

    def test_sso_account_created_without_a_password_is_not_flagged(self):
        admin = self.make_admin('user.create')
        self.client.force_authenticate(admin)

        resp = self.client.post(
            self.users_url,
            {'email': 'sso@example.com', 'full_name': 'SSO Person',
             'login_type': LoginType.SSO},
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.content)

        created = User.objects.get(email='sso@example.com')
        self.assertFalse(created.has_usable_password())
        # A local user in this state is told to change their password; an SSO
        # one never will, so flagging it would strand the account.
        self.assertFalse(created.must_change_password)

    def test_a_local_account_without_a_password_is_flagged(self):
        admin = self.make_admin('user.create')
        self.client.force_authenticate(admin)

        self.client.post(
            self.users_url,
            {'email': 'local@example.com', 'full_name': 'Local Person'},
            format='json',
        )
        self.assertTrue(
            User.objects.get(email='local@example.com').must_change_password
        )

    def test_an_sso_account_cannot_sign_in_with_a_password(self):
        User.objects.create_user(
            'sso@example.com', full_name='SSO', login_type=LoginType.SSO
        )
        resp = self.login(email='sso@example.com', password=PASSWORD)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()['code'], 'invalid_credentials')
