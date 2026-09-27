from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Role, User, UserNote


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
            {'email': 'new@example.com', 'full_name': 'New User', 'password': 'Str0ng-pass-word!', 'role_id': str(self.role.pk)},
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
                {'field': 'role', 'from': '', 'to': 'Staff'},
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

    def test_patch_without_change_writes_no_note(self):
        user = User.objects.create_user(email='u@example.com', password='Str0ng-pass-word!', full_name='U')
        self.client.patch(self.url('detail', user.pk), {'full_name': 'U'}, format='json')
        self.assertFalse(user.notes.exists())

    def test_roles_list(self):
        Role.objects.create(name='Admin')
        Role.objects.create(name='Old', is_active=False)
        response = self.client.get(reverse('accounts:apis:roles:list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([role['name'] for role in response.data['data']], ['Admin', 'Staff'])
