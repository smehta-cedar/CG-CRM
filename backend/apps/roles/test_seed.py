"""Phase 5: the seed command."""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .models import Permission, Role

User = get_user_model()


class SeedCommandTests(TestCase):
    def seed(self, *args, **kwargs):
        out = StringIO()
        call_command('seed', *args, stdout=out, stderr=out, **kwargs)
        return out.getvalue()

    def test_creates_the_role_with_every_permission(self):
        self.seed('--skip-admin')

        role = Role.objects.get(name='Super Admin')
        self.assertEqual(
            set(role.permissions.values_list('codename', flat=True)),
            set(Permission.objects.values_list('codename', flat=True)),
        )

    def test_creates_the_admin_user(self):
        self.seed('--email', 'boss@example.com', '--password', 'a-long-passphrase')

        user = User.objects.get(email='boss@example.com')
        self.assertEqual(user.role.name, 'Super Admin')
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password('a-long-passphrase'))

    def test_a_chosen_password_does_not_force_a_change(self):
        self.seed('--email', 'boss@example.com', '--password', 'a-long-passphrase')
        self.assertFalse(User.objects.get(email='boss@example.com').must_change_password)

    def test_a_generated_password_is_printed_and_must_be_changed(self):
        output = self.seed('--email', 'boss@example.com')

        user = User.objects.get(email='boss@example.com')
        self.assertTrue(user.must_change_password)

        # The printed password has to be the one that actually works, or the
        # handover is broken.
        printed = [
            line.split('Password:')[1].strip()
            for line in output.splitlines() if 'Password:' in line
        ]
        self.assertEqual(len(printed), 1)
        self.assertTrue(user.check_password(printed[0]))

    def test_generated_passwords_differ_between_runs(self):
        first = self.seed('--email', 'a@example.com')
        second = self.seed('--email', 'b@example.com')
        self.assertNotEqual(first, second)

    def test_email_is_normalised(self):
        self.seed('--email', 'BOSS@Example.COM', '--password', 'a-long-passphrase')
        self.assertTrue(User.objects.filter(email='boss@example.com').exists())

    def test_requires_an_email_unless_skipping_the_admin(self):
        with self.assertRaises(CommandError):
            self.seed()

    def test_is_idempotent(self):
        self.seed('--email', 'boss@example.com', '--password', 'a-long-passphrase')
        self.seed('--email', 'boss@example.com', '--password', 'a-long-passphrase')

        self.assertEqual(User.objects.filter(email='boss@example.com').count(), 1)
        self.assertEqual(Role.objects.filter(name='Super Admin').count(), 1)
        self.assertEqual(Permission.objects.count(), 10)

    def test_rerunning_never_resets_an_existing_password(self):
        """Otherwise the command is a way to take over an account."""
        self.seed('--email', 'boss@example.com', '--password', 'the-original-passphrase')
        self.seed('--email', 'boss@example.com', '--password', 'an-attackers-passphrase')

        user = User.objects.get(email='boss@example.com')
        self.assertTrue(user.check_password('the-original-passphrase'))
        self.assertFalse(user.check_password('an-attackers-passphrase'))

    def test_tops_up_the_role_when_the_catalog_grows(self):
        self.seed('--skip-admin')
        role = Role.objects.get(name='Super Admin')

        added = Permission.objects.create(
            module='Billing', resource='Invoice', action='create',
            codename='invoice.create',
        )
        role.permissions.remove(added)
        self.assertNotIn('invoice.create', set(
            role.permissions.values_list('codename', flat=True)))

        output = self.seed('--skip-admin')
        self.assertIn('invoice.create', set(
            role.permissions.values_list('codename', flat=True)))
        self.assertIn('topped up', output)

    def test_reports_permissions_not_in_the_catalog(self):
        Permission.objects.create(
            module='Gone', resource='Ghost', action='haunt', codename='ghost.haunt',
        )
        output = self.seed('--skip-admin')
        self.assertIn('ghost.haunt', output)
        self.assertIn('--prune', output)

    def test_reads_settings_from_the_environment(self):
        import os

        os.environ['CRM_ADMIN_EMAIL'] = 'env@example.com'
        os.environ['CRM_ADMIN_PASSWORD'] = 'a-long-passphrase'
        os.environ['CRM_ADMIN_NAME'] = 'Env Admin'
        try:
            self.seed()
        finally:
            for key in ('CRM_ADMIN_EMAIL', 'CRM_ADMIN_PASSWORD', 'CRM_ADMIN_NAME'):
                os.environ.pop(key, None)

        user = User.objects.get(email='env@example.com')
        self.assertEqual(user.full_name, 'Env Admin')
        self.assertTrue(user.check_password('a-long-passphrase'))

    def test_the_seeded_admin_can_sign_in_and_use_the_api(self):
        """End to end: the command's output is a working account."""
        self.seed('--email', 'boss@example.com', '--password', 'a-long-passphrase')

        resp = self.client.post(
            '/api/v1/auth/login/',
            {'email': 'boss@example.com', 'password': 'a-long-passphrase'},
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertFalse(body['must_change_password'])
        self.assertEqual(body['user']['role']['name'], 'Super Admin')
        self.assertEqual(len(body['user']['permissions']), 10)

        self.client.defaults['HTTP_AUTHORIZATION'] = f"Bearer {body['access']}"
        self.assertEqual(self.client.get('/api/v1/roles/').status_code, 200)
        self.assertEqual(self.client.get('/api/v1/users/').status_code, 200)

    def test_a_generated_password_admin_is_gated_until_they_change_it(self):
        output = self.seed('--email', 'boss@example.com')
        password = next(
            line.split('Password:')[1].strip()
            for line in output.splitlines() if 'Password:' in line
        )

        body = self.client.post(
            '/api/v1/auth/login/',
            {'email': 'boss@example.com', 'password': password},
            content_type='application/json',
        ).json()
        self.assertTrue(body['must_change_password'])

        self.client.defaults['HTTP_AUTHORIZATION'] = f"Bearer {body['access']}"
        resp = self.client.get('/api/v1/roles/')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()['code'], 'password_change_required')
