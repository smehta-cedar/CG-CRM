from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Role, RolePermission, User
from apps.agents.models import Agent
from apps.carriers.models import Carrier

from .models import Notification


class NotificationTestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='Sup3r-secret!', full_name='Admin')
        admin_role = Role.objects.create(name='Admin')
        staff_role = Role.objects.create(name='Staff')
        RolePermission.objects.create(role=staff_role, module='requests', can_view=True, can_create=True)
        self.role_admin = User.objects.create_user(email='boss@example.com', password='x', full_name='Boss', role=admin_role)
        self.staff = User.objects.create_user(email='staff@example.com', password='x', full_name='Sam Staff', role=staff_role)
        self.agent = Agent.objects.create(name='Maria Alva', npn='1')
        self.carrier = Carrier.objects.create(name='Humana', lines_of_business=['MAPD'])

    def file_request(self, user):
        self.client.force_authenticate(user)
        response = self.client.post(
            reverse('requests:apis:requests:create'),
            {'type': 'licensing', 'agent_id': str(self.agent.pk), 'carrier_id': str(self.carrier.pk), 'state': 'TX'},
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)

    def url(self, name, *args):
        return reverse(f'notifications:apis:notifications:{name}', args=args)


class NotifyOnRequestTests(NotificationTestCase):
    def test_filing_notifies_every_admin(self):
        self.file_request(self.staff)
        recipients = set(Notification.objects.values_list('recipient__email', flat=True))
        self.assertEqual(recipients, {'admin@example.com', 'boss@example.com'})
        notification = Notification.objects.get(recipient=self.admin)
        self.assertEqual(notification.title, 'Sam Staff filed a licensing request')
        self.assertEqual(notification.body, 'Maria Alva · Humana in TX')
        self.assertEqual(notification.link, '/hr')

    def test_an_admin_filer_is_notified_too(self):
        self.file_request(self.admin)
        recipients = set(Notification.objects.values_list('recipient__email', flat=True))
        self.assertEqual(recipients, {'admin@example.com', 'boss@example.com'})

    def test_blocked_admins_are_skipped(self):
        self.role_admin.is_active = False
        self.role_admin.save()
        self.file_request(self.staff)
        self.assertEqual(list(Notification.objects.values_list('recipient__email', flat=True)), ['admin@example.com'])


class NotificationAPITests(NotificationTestCase):
    def test_lists_only_my_own_with_unread_count(self):
        self.file_request(self.staff)
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.url('list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['data']), 1)
        self.assertEqual(response.data['meta']['unread'], 1)

        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get(self.url('list')).data['data'], [])

    def test_marks_one_read(self):
        self.file_request(self.staff)
        notification = Notification.objects.get(recipient=self.admin)
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.url('read', notification.pk))
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data['data']['read_at'])

    def test_cannot_mark_someone_elses(self):
        self.file_request(self.staff)
        notification = Notification.objects.get(recipient=self.admin)
        self.client.force_authenticate(self.role_admin)
        self.assertEqual(self.client.post(self.url('read', notification.pk)).status_code, 404)

    def test_marks_all_read(self):
        self.file_request(self.staff)
        self.file_request(self.staff)
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.url('read-all'))
        self.assertEqual(response.data['data'], {'marked': 2})
        self.assertEqual(self.client.get(self.url('list')).data['meta']['unread'], 0)
