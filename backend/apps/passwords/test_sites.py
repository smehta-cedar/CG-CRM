from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Role, RolePermission, User
from apps.agency.models import Agency
from apps.agents.models import Agent
from apps.carriers.models import Carrier

from .models import Site, SitePassword, SitePasswordNote


class SiteAPITestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='Sup3r-secret!', full_name='Admin')
        self.client.force_authenticate(self.admin)
        self.agent = Agent.objects.create(name='Maria Alva', npn='1')
        self.other_agent = Agent.objects.create(name='James Carter', npn='2')
        self.agency = Agency.objects.create(name='Cedar Grove')
        self.site = Site.objects.create(name='Sunfire')
        self.other_site = Site.objects.create(name='Medicare.gov')
        self.sample = {
            'agent_id': str(self.agent.pk),
            'site_id': str(self.site.pk),
            'username': 'malva',
            'portal_password': 'pass 1 ',
        }

    def make_password(self, **overrides):
        fields = {'agent': self.agent, 'site': self.site, 'username': 'malva', 'portal_password': 'p', **overrides}
        return SitePassword.objects.create(**fields)

    def url(self, name, *args):
        return reverse(f'passwords:apis:{name}', args=args)


class SiteTests(SiteAPITestCase):
    def test_creates_site_trimmed(self):
        response = self.client.post(self.url('sites:create'), {'name': '  Quote Tool '}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['data']['name'], 'Quote Tool')
        self.assertEqual(response.data['data']['password_count'], 0)

    def test_rejects_name_taken_in_another_case(self):
        response = self.client.post(self.url('sites:create'), {'name': 'SUNFIRE'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['name'], ['A site with this name already exists.'])

    def test_rejects_blank_name(self):
        response = self.client.post(self.url('sites:create'), {'name': '  '}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('name', response.data['errors'])

    def test_deleted_site_name_can_be_reused(self):
        self.other_site.delete()
        response = self.client.post(self.url('sites:create'), {'name': 'medicare.gov'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def test_lists_by_name_with_counts(self):
        self.make_password()
        self.make_password(agent=self.other_agent).delete()
        response = self.client.get(self.url('sites:list'))
        self.assertEqual(
            [(row['name'], row['password_count']) for row in response.data['data']],
            [('Medicare.gov', 0), ('Sunfire', 1)],
        )

    def test_rename_allows_a_case_change(self):
        response = self.client.patch(self.url('sites:detail', self.site.pk), {'name': 'SunFire'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['name'], 'SunFire')

    def test_rename_rejects_another_sites_name(self):
        response = self.client.patch(self.url('sites:detail', self.site.pk), {'name': 'medicare.GOV'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('name', response.data['errors'])

    def test_delete_refused_while_passwords_use_it(self):
        self.make_password()
        response = self.client.delete(self.url('sites:detail', self.site.pk))
        self.assertEqual(response.status_code, 400)
        self.assertIn('site', response.data['errors'])

    def test_delete_unused_site(self):
        response = self.client.delete(self.url('sites:detail', self.other_site.pk))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Site.objects.filter(pk=self.other_site.pk).exists())


class SiteLinkTests(SiteAPITestCase):
    def test_creates_and_updates_link(self):
        response = self.client.post(
            self.url('sites:create'), {'name': 'Quote Tool', 'link': 'https://quote.example.com'}, format='json'
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['data']['link'], 'https://quote.example.com')
        site_id = response.data['data']['id']
        response = self.client.patch(self.url('sites:detail', site_id), {'link': ''}, format='json')
        self.assertEqual(response.data['data']['link'], '')

    def test_rejects_invalid_link(self):
        response = self.client.post(self.url('sites:create'), {'name': 'X', 'link': 'not a url'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('link', response.data['errors'])

    def test_site_password_carries_the_sites_link(self):
        self.site.link = 'https://sunfire.example.com'
        self.site.save(update_fields=['link'])
        response = self.client.post(self.url('site_passwords:create'), self.sample, format='json')
        self.assertEqual(response.data['data']['site']['link'], 'https://sunfire.example.com')


class PendingCredentialsTests(SiteAPITestCase):
    def test_pending_needs_no_username_or_password(self):
        sample = {'agent_id': str(self.agent.pk), 'site_id': str(self.site.pk), 'status': 'pending'}
        response = self.client.post(self.url('site_passwords:create'), sample, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual((response.data['data']['username'], response.data['data']['portal_password']), ('', ''))

    def test_active_needs_both(self):
        sample = {'agent_id': str(self.agent.pk), 'site_id': str(self.site.pk), 'username': ' '}
        response = self.client.post(self.url('site_passwords:create'), sample, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.data['errors']), {'username', 'portal_password'})

    def test_leaving_pending_needs_both(self):
        password = self.make_password(username='', portal_password='', status='pending')
        response = self.client.patch(self.url('site_passwords:detail', password.pk), {'status': 'active'}, format='json')
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(
            self.url('site_passwords:detail', password.pk),
            {'status': 'active', 'username': 'malva', 'portal_password': 'p'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)


class SitePasswordTests(SiteAPITestCase):
    def test_creates_with_note(self):
        response = self.client.post(self.url('site_passwords:create'), self.sample, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data['data']
        self.assertEqual(data['site'], {'id': str(self.site.pk), 'name': 'Sunfire', 'link': ''})
        self.assertEqual(data['portal_password'], 'pass 1 ')
        self.assertEqual(
            SitePasswordNote.objects.get(password_id=data['id']).changes,
            [
                {'field': 'agent', 'from': '', 'to': 'Maria Alva'},
                {'field': 'site', 'from': '', 'to': 'Sunfire'},
                {'field': 'username', 'from': '', 'to': 'malva'},
                {'field': 'password', 'from': '', 'to': '', 'redacted': True},
                {'field': 'status', 'from': '', 'to': 'active'},
            ],
        )

    def test_rejects_second_password_for_same_pair(self):
        self.make_password()
        response = self.client.post(self.url('site_passwords:create'), self.sample, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['site_id'], ['Maria Alva already has a password at Sunfire.'])

    def test_agency_and_another_agent_can_share_a_site(self):
        self.make_password()
        for extra in ({'agent_id': str(self.other_agent.pk)}, {'agent_id': None, 'agency_id': str(self.agency.pk)}):
            response = self.client.post(self.url('site_passwords:create'), {**self.sample, **extra}, format='json')
            self.assertEqual(response.status_code, 201, response.data)

    def test_rejects_deleted_site(self):
        self.site.delete()
        response = self.client.post(self.url('site_passwords:create'), self.sample, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('site_id', response.data['errors'])

    def test_rejects_blank_password_and_missing_party(self):
        response = self.client.post(
            self.url('site_passwords:create'), {**self.sample, 'portal_password': ' '}, format='json'
        )
        self.assertIn('portal_password', response.data['errors'])
        response = self.client.post(self.url('site_passwords:create'), {**self.sample, 'agent_id': None}, format='json')
        self.assertIn('agent_id', response.data['errors'])

    def test_patch_moves_site_and_notes_it(self):
        password = self.make_password()
        response = self.client.patch(
            self.url('site_passwords:detail', password.pk), {'site_id': str(self.other_site.pk)}, format='json'
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(password.notes.get().changes, [{'field': 'site', 'from': 'Sunfire', 'to': 'Medicare.gov'}])

    def test_list_filters_and_search(self):
        self.make_password()
        self.make_password(agent=self.other_agent, site=self.other_site)
        response = self.client.get(self.url('site_passwords:list'), {'site_id': str(self.site.pk)})
        self.assertEqual([row['agent']['name'] for row in response.data['data']], ['Maria Alva'])
        response = self.client.get(self.url('site_passwords:list'), {'search': 'medicare'})
        self.assertEqual([row['agent']['name'] for row in response.data['data']], ['James Carter'])

    def test_site_passwords_stay_out_of_carrier_passwords(self):
        self.make_password()
        response = self.client.get(reverse('passwords:apis:passwords:list'))
        self.assertEqual(response.data['data'], [])

    def test_needs_the_passwords_module(self):
        staff = User.objects.create_user(email='staff@example.com', password='Sup3r-secret!', full_name='Staff')
        self.client.force_authenticate(staff)
        self.assertEqual(self.client.get(self.url('site_passwords:list')).status_code, 403)
        self.assertEqual(self.client.get(self.url('sites:list')).status_code, 403)
        role = Role.objects.create(name='passwords-view')
        RolePermission.objects.create(role=role, module='passwords', can_view=True)
        staff.roles.set([role])
        # A fresh user object: permissions are cached on the one that got the 403s.
        self.client.force_authenticate(User.objects.get(pk=staff.pk))
        self.assertEqual(self.client.get(self.url('sites:list')).status_code, 200)
        self.assertEqual(self.client.post(self.url('sites:create'), {'name': 'X'}, format='json').status_code, 403)


class SplitSitesMigrationTests(TransactionTestCase):
    """0008 undoes 0007: a site naming a carrier gets the carrier back, any
    other becomes a site password (deleted ones too, with their notes)."""

    before = [('passwords', '0007_password_site')]
    after = [('passwords', '0008_restore_carrier_add_sites')]

    def migrate(self, targets):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(targets)
        return executor.loader.project_state(targets).apps

    def tearDown(self):
        call_command('migrate', verbosity=0)

    def test_splits_carrier_names_from_other_sites(self):
        old = self.migrate(self.before)
        # Agents and carriers are made with today's models: only passwords went back.
        agent = Agent.objects.create(name='Maria Alva', npn='1')
        Carrier.objects.create(name='Humana', lines_of_business=['MAPD'])
        OldPassword = old.get_model('passwords', 'Password')
        OldPassword.objects.create(agent_id=agent.pk, site='HUMANA', username='a', portal_password='p')
        moved = OldPassword.objects.create(agent_id=agent.pk, site='Quote Tool', username='b', portal_password='q')
        OldPassword.objects.filter(pk=moved.pk).update(deleted_at=moved.created_at)
        old.get_model('passwords', 'PasswordNote').objects.create(password=moved, kind='added', changes=[])

        new = self.migrate(self.after)
        Password = new.get_model('passwords', 'Password')
        SitePassword = new.get_model('passwords', 'SitePassword')
        self.assertEqual([(p.username, p.carrier.name) for p in Password.objects.all()], [('a', 'Humana')])
        site_password = SitePassword.objects.get()
        self.assertEqual((site_password.username, site_password.site.name), ('b', 'Quote Tool'))
        self.assertIsNotNone(site_password.deleted_at)
        self.assertEqual(new.get_model('passwords', 'SitePasswordNote').objects.filter(password=site_password).count(), 1)
