import re

from django.core import mail
from django.core.cache import cache
from django.urls import reverse
from django_otp.plugins.otp_email.models import EmailDevice
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.agents.models import Agent


def make_agent(**overrides):
    fields = {
        'name': 'Maria Alva',
        'npn': '17654321',
        'email': 'maria.alvarez@example.com',
    }
    fields.update(overrides)
    return Agent.objects.create(**fields)


class AgentAuthTestCase(APITestCase):
    def setUp(self):
        # Both endpoints share the 'auth' throttle, which counts in the cache.
        cache.clear()

    def code_url(self):
        return reverse('accounts:apis:auth:agent-code')

    def login_url(self):
        return reverse('accounts:apis:auth:agent-login')

    def home_url(self):
        return reverse('accounts:apis:auth:agent')

    def request_code(self, email):
        return self.client.post(self.code_url(), {'email': email}, format='json')

    def emailed_code(self):
        """The six digits in the last email sent."""
        return re.search(r'\b\d{6}\b', mail.outbox[-1].body).group()

    def sign_in(self, email, code):
        return self.client.post(self.login_url(), {'email': email, 'code': code}, format='json')


class AgentCodeRequestTests(AgentAuthTestCase):
    def test_emails_a_new_random_code_to_the_work_email(self):
        make_agent()
        response = self.request_code('Maria.Alvarez@example.com')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['maria.alvarez@example.com'])
        self.assertNotIn(self.emailed_code(), str(response.data))

    def test_unknown_shared_inactive_or_staff_email_gets_the_same_reply_and_no_mail(self):
        sent = self.request_code('nobody@example.com')
        make_agent(name='Shared One', npn='10000006', email='shared@example.com')
        make_agent(name='Shared Two', npn='10000007', email='shared@example.com')
        make_agent(name='Inactive', npn='10000008', email='inactive@example.com', is_active=False)
        User.objects.create_user(email='staff@example.com', password='Sup3r-secret!', full_name='Staff')
        make_agent(name='Staff Email', npn='10000009', email='staff@example.com')
        replies = [
            self.request_code(email)
            for email in ('shared@example.com', 'inactive@example.com', 'staff@example.com')
        ]
        self.assertEqual(len(mail.outbox), 0)
        for reply in replies:
            self.assertEqual(reply.status_code, 200)
            self.assertEqual(reply.data, sent.data)

    def test_deleted_agent_gets_no_mail(self):
        make_agent().delete()
        self.assertEqual(self.request_code('maria.alvarez@example.com').status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_email_must_be_an_email(self):
        response = self.request_code('not-an-email')
        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.data['errors'])

    def test_a_second_request_within_the_cooldown_sends_nothing(self):
        make_agent()
        self.request_code('maria.alvarez@example.com')
        again = self.request_code('maria.alvarez@example.com')
        self.assertEqual(again.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)


class AgentLoginTests(AgentAuthTestCase):
    def test_signs_in_with_the_emailed_code(self):
        agent = make_agent()
        self.request_code('maria.alvarez@example.com')
        response = self.sign_in('Maria.Alvarez@example.com', self.emailed_code())
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data['data']
        self.assertIn('access', data)
        self.assertIn('refresh', data)
        user = User.objects.get(email='maria.alvarez@example.com')
        self.assertEqual(str(data['user']['agent_id']), str(agent.pk))
        self.assertEqual(user.agent_id, agent.pk)
        self.assertFalse(user.has_usable_password())

    def test_a_code_works_once(self):
        make_agent()
        self.request_code('maria.alvarez@example.com')
        code = self.emailed_code()
        self.assertEqual(self.sign_in('maria.alvarez@example.com', code).status_code, 200)
        again = self.sign_in('maria.alvarez@example.com', code)
        self.assertEqual(again.status_code, 401)
        self.assertEqual(again.data['code'], 'invalid_credentials')

    def test_an_expired_code_is_refused(self):
        make_agent()
        self.request_code('maria.alvarez@example.com')
        code = self.emailed_code()
        EmailDevice.objects.update(valid_until='2000-01-01T00:00:00Z')
        self.assertEqual(self.sign_in('maria.alvarez@example.com', code).status_code, 401)

    def test_wrong_code_and_unknown_email_look_the_same(self):
        make_agent()
        self.request_code('maria.alvarez@example.com')
        code = self.emailed_code()
        wrong = self.sign_in('maria.alvarez@example.com', '111111' if code == '000000' else '000000')
        unknown = self.sign_in('nobody@example.com', code)
        for response in (wrong, unknown):
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.data['code'], 'invalid_credentials')
        self.assertEqual(wrong.data['message'], unknown.data['message'])

    def test_agent_made_inactive_after_the_email_is_blocked(self):
        agent = make_agent()
        self.request_code('maria.alvarez@example.com')
        agent.is_active = False
        agent.save()
        response = self.sign_in('maria.alvarez@example.com', self.emailed_code())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['code'], 'account_blocked')

    def test_home_is_this_agent_only(self):
        agent = make_agent()
        other = make_agent(name='Other Agent', npn='10000009', email='other@example.com')
        self.request_code(agent.email)
        self.sign_in(agent.email, self.emailed_code())
        user = User.objects.get(agent=agent)
        self.client.force_authenticate(user)
        response = self.client.get(self.home_url())
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['agent']['id'], str(agent.pk))
        self.assertEqual(response.data['data']['contracts'], [])
        self.assertEqual(response.data['data']['certifications'], [])
        self.assertNotEqual(response.data['data']['agent']['id'], str(other.pk))

    def test_staff_home_is_not_found(self):
        staff = User.objects.create_user(email='staff@example.com', password='Sup3r-secret!', full_name='Staff')
        self.client.force_authenticate(staff)
        response = self.client.get(self.home_url())
        self.assertEqual(response.status_code, 404)
