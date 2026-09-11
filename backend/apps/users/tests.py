from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase

from .models import LoginType

User = get_user_model()


class UserManagerTests(TestCase):
    def test_create_user_defaults(self):
        user = User.objects.create_user('Ada@Example.COM', 'pw', full_name='Ada Lovelace')

        self.assertEqual(user.email, 'ada@example.com')  # fully lowercased
        self.assertTrue(user.check_password('pw'))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_blocked)
        self.assertFalse(user.must_change_password)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.login_type, LoginType.LOCAL)
        self.assertIsNotNone(user.created_at)

    def test_create_user_without_password_is_unusable(self):
        user = User.objects.create_user(
            'sso@example.com', full_name='Essoh', login_type=LoginType.SSO
        )
        self.assertFalse(user.has_usable_password())

    def test_email_is_required(self):
        with self.assertRaises(ValueError):
            User.objects.create_user('', 'pw', full_name='Nobody')

    def test_full_name_is_required(self):
        with self.assertRaises(ValidationError):
            User.objects.create_user('x@example.com', 'pw')

    def test_email_is_unique_case_insensitively(self):
        User.objects.create_user('dup@example.com', 'pw', full_name='First')
        with self.assertRaises(ValidationError):
            User.objects.create_user('DUP@Example.com', 'pw', full_name='Second')

    def test_save_normalises_email_outside_the_manager(self):
        user = User(email='Raw@Example.COM', full_name='Raw')
        user.set_password('pw')
        user.save()
        self.assertEqual(User.objects.get(pk=user.pk).email, 'raw@example.com')

    def test_get_by_natural_key_is_case_insensitive(self):
        user = User.objects.create_user('nat@example.com', 'pw', full_name='Nat')
        self.assertEqual(User.objects.get_by_natural_key('NAT@example.com'), user)

    def test_create_superuser(self):
        admin = User.objects.create_superuser(
            'admin@example.com', 'pw', full_name='Admin User'
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_active)
        self.assertFalse(admin.must_change_password)

    def test_create_superuser_rejects_contradictory_flags(self):
        for flags in ({'is_staff': False}, {'is_superuser': False}):
            with self.subTest(**flags):
                with self.assertRaises(ValueError):
                    User.objects.create_superuser(
                        'bad@example.com', 'pw', full_name='Bad', **flags
                    )


class UserModelTests(TestCase):
    def test_str_and_name_helpers(self):
        user = User.objects.create_user('grace@example.com', 'pw', full_name='Grace Hopper')
        self.assertEqual(str(user), 'grace@example.com')
        self.assertEqual(user.get_full_name(), 'Grace Hopper')
        self.assertEqual(user.get_short_name(), 'Grace')

    def test_can_sign_in_requires_active_and_unblocked(self):
        user = User.objects.create_user('flags@example.com', 'pw', full_name='Flags')
        self.assertTrue(user.can_sign_in)

        user.is_blocked = True
        self.assertFalse(user.can_sign_in)

        user.is_blocked, user.is_active = False, False
        self.assertFalse(user.can_sign_in)

    def test_username_field_is_email(self):
        self.assertEqual(User.USERNAME_FIELD, 'email')
        self.assertEqual(User.REQUIRED_FIELDS, ['full_name'])


class AuthenticationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            'login@example.com', 'correct-horse', full_name='Login Tester'
        )

    def test_authenticates_with_email_in_any_case(self):
        self.assertEqual(
            authenticate(username='LOGIN@example.com', password='correct-horse'),
            self.user,
        )

    def test_wrong_password_fails(self):
        self.assertIsNone(
            authenticate(username='login@example.com', password='nope')
        )

    def test_blocked_user_cannot_authenticate(self):
        self.user.is_blocked = True
        self.user.save(update_fields=['is_blocked'])
        self.assertIsNone(
            authenticate(username='login@example.com', password='correct-horse')
        )

    def test_inactive_user_cannot_authenticate(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.assertIsNone(
            authenticate(username='login@example.com', password='correct-horse')
        )


class JWTEndpointTests(TestCase):
    """The token endpoints were wired up before the custom user existed."""

    url = '/api/v1/auth/token/'

    def setUp(self):
        self.user = User.objects.create_user(
            'jwt@example.com', 's3cret-pass', full_name='JWT Tester'
        )

    def obtain(self, email='jwt@example.com', password='s3cret-pass'):
        return self.client.post(
            self.url,
            {'email': email, 'password': password},
            content_type='application/json',
        )

    def test_obtain_pair_keys_off_email(self):
        resp = self.obtain(email='JWT@Example.com')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(sorted(resp.json()), ['access', 'refresh'])

    def test_refresh_rotates(self):
        refresh = self.obtain().json()['refresh']
        resp = self.client.post(
            '/api/v1/auth/token/refresh/',
            {'refresh': refresh},
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('access', resp.json())

    def test_blocked_user_is_refused_a_token(self):
        self.user.is_blocked = True
        self.user.save(update_fields=['is_blocked'])
        self.assertEqual(self.obtain().status_code, 401)

    def test_inactive_user_is_refused_a_token(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.assertEqual(self.obtain().status_code, 401)


class AdminTests(TestCase):
    """`manage.py check` validates the fieldsets, but not that the forms build."""

    def setUp(self):
        from django.contrib import admin

        self.model_admin = admin.site._registry[User]
        self.request = RequestFactory().get('/')
        self.request.user = User.objects.create_superuser(
            'root@example.com', 'pw', full_name='Root User'
        )

    def test_add_form_builds_and_renders(self):
        form = self.model_admin.get_form(self.request, obj=None)()
        self.assertIn('email', form.fields)
        self.assertIn('full_name', form.fields)
        self.assertIn('usable_password', form.fields)
        self.assertTrue(str(form))

    def test_change_form_exposes_the_status_flags(self):
        form = self.model_admin.get_form(self.request, obj=self.request.user)()
        for name in ('email', 'full_name', 'login_type', 'is_blocked',
                     'must_change_password', 'is_active'):
            self.assertIn(name, form.fields, name)
        self.assertTrue(str(form))


class CreateSuperuserCommandTests(TestCase):
    def test_noinput_run(self):
        from io import StringIO

        from django.core.management import call_command

        call_command(
            'createsuperuser',
            interactive=False,
            email='cli@example.com',
            full_name='CLI Admin',
            stdout=StringIO(),
        )
        admin_user = User.objects.get(email='cli@example.com')
        self.assertTrue(admin_user.is_superuser)
        self.assertTrue(admin_user.is_staff)
        self.assertFalse(admin_user.has_usable_password())  # set later via changepassword
