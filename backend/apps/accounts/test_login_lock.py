from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from django_otp.plugins.otp_email.models import EmailDevice
from rest_framework.test import APITestCase

from apps.accounts.models import User

from .test_agent_login import AgentAuthTestCase, make_agent

PASSWORD = 'Sup3r-secret!'


class StaffLoginLockTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(email='staff@example.com', password=PASSWORD, full_name='Staff')

    def log_in(self, password):
        url = reverse('accounts:apis:auth:login')
        return self.client.post(url, {'email': 'staff@example.com', 'password': password}, format='json')

    def test_fifth_wrong_password_in_a_row_locks_the_account(self):
        for _ in range(4):
            self.assertEqual(self.log_in('wrong').data['code'], 'invalid_credentials')
        fifth = self.log_in('wrong')
        self.assertEqual(fifth.status_code, 403)
        self.assertEqual(fifth.data['code'], 'account_locked')
        # The right password is refused too while the lock lasts.
        self.assertEqual(self.log_in(PASSWORD).data['code'], 'account_locked')

    def test_a_good_login_resets_the_count(self):
        for _ in range(4):
            self.log_in('wrong')
        self.assertEqual(self.log_in(PASSWORD).status_code, 200)
        self.assertEqual(self.log_in('wrong').data['code'], 'invalid_credentials')

    def test_the_lock_ends_by_itself(self):
        User.objects.filter(pk=self.user.pk).update(locked_until=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.log_in(PASSWORD).status_code, 200)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.locked_until)


class AgentLoginLockTests(AgentAuthTestCase):
    def setUp(self):
        super().setUp()
        make_agent()
        self.request_code('maria.alvarez@example.com')
        self.code = self.emailed_code()
        self.wrong = '111111' if self.code == '000000' else '000000'

    def test_fifth_wrong_code_in_a_row_locks_the_account(self):
        for _ in range(4):
            self.assertEqual(self.sign_in('maria.alvarez@example.com', self.wrong).data['code'], 'invalid_credentials')
        fifth = self.sign_in('maria.alvarez@example.com', self.wrong)
        self.assertEqual(fifth.status_code, 403)
        self.assertEqual(fifth.data['code'], 'account_locked')
        self.assertEqual(self.sign_in('maria.alvarez@example.com', self.code).data['code'], 'account_locked')

    def test_no_new_code_is_sent_while_locked(self):
        User.objects.filter(email='maria.alvarez@example.com').update(locked_until=timezone.now() + timedelta(minutes=5))
        # Past the one-minute wait between emails, so only the lock stops this one.
        EmailDevice.objects.update(last_generated_timestamp=None)
        mail.outbox.clear()
        self.assertEqual(self.request_code('maria.alvarez@example.com').status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_wrong_passwords_on_the_staff_form_do_not_lock_an_agent(self):
        url = reverse('accounts:apis:auth:login')
        for _ in range(5):
            self.client.post(url, {'email': 'maria.alvarez@example.com', 'password': 'wrong'}, format='json')
        self.assertEqual(self.sign_in('maria.alvarez@example.com', self.code).status_code, 200)
