import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Role, RolePermission, User
from apps.agents.models import Agent

from .models import Certification, CertificationNote, PolicyType


def make_agent(name='Maria Alva', npn='17654321', **overrides):
    return Agent.objects.create(name=name, npn=npn, **overrides)


def make_policy_type(name='Medicare Advantage', **overrides):
    return PolicyType.objects.create(name=name, **overrides)


def make_certification(agent, policy_type, **overrides):
    return Certification.objects.create(agent=agent, policy_type=policy_type, **overrides)


def make_role(module, **flags):
    role = Role.objects.create(name=f"{module}-{'-'.join(k for k, v in flags.items() if v) or 'none'}")
    RolePermission.objects.create(role=role, module=module, **flags)
    return role


class CertificationAPITestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='Sup3r-secret!', full_name='Admin')
        self.client.force_authenticate(self.admin)
        self.agent = make_agent()
        self.policy_type = make_policy_type()
        self.sample = {
            'agent': str(self.agent.pk),
            'policy_type': str(self.policy_type.pk),
            'start_date': '2026-01-01',
            'end_date': '2026-12-31',
        }

    def list_url(self):
        return reverse('policies:apis:certifications:list')

    def create_url(self):
        return reverse('policies:apis:certifications:create')

    def detail_url(self, certification):
        return reverse('policies:apis:certifications:detail', args=[certification.pk])

    def notes_url(self, certification):
        return reverse('policies:apis:certifications:notes', args=[certification.pk])

    def file_url(self, certification):
        return reverse('policies:apis:certifications:file', args=[certification.pk])


class CertificationCreateTests(CertificationAPITestCase):
    def test_creates_certification_from_sample(self):
        response = self.client.post(self.create_url(), self.sample, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data['data']
        self.assertEqual(data['agent']['name'], 'Maria Alva')
        self.assertEqual(data['policy_type']['name'], 'Medicare Advantage')
        self.assertEqual(data['start_date'], '2026-01-01')
        self.assertEqual(data['end_date'], '2026-12-31')
        self.assertTrue(data['is_active'])
        self.assertEqual(Certification.objects.get(pk=data['id']).created_by, self.admin)

    def test_records_an_added_note_in_field_order(self):
        response = self.client.post(self.create_url(), self.sample, format='json')
        note = CertificationNote.objects.get(certification_id=response.data['data']['id'])
        self.assertEqual(note.kind, 'added')
        self.assertEqual(note.created_by, self.admin)
        self.assertEqual(
            note.changes,
            [
                {'field': 'agent', 'from': '', 'to': 'Maria Alva'},
                {'field': 'policy_type', 'from': '', 'to': 'Medicare Advantage'},
                {'field': 'start_date', 'from': '', 'to': '2026-01-01'},
                {'field': 'end_date', 'from': '', 'to': '2026-12-31'},
                {'field': 'is_verified', 'from': '', 'to': 'no'},
                {'field': 'status', 'from': '', 'to': 'active'},
            ],
        )

    def test_dates_are_optional(self):
        body = {'agent': str(self.agent.pk), 'policy_type': str(self.policy_type.pk)}
        response = self.client.post(self.create_url(), body, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNone(response.data['data']['start_date'])
        self.assertIsNone(response.data['data']['end_date'])
        # Blank dates are not listed on the note.
        note = CertificationNote.objects.get(certification_id=response.data['data']['id'])
        self.assertEqual([change['field'] for change in note.changes], ['agent', 'policy_type', 'is_verified', 'status'])

    def test_blank_and_null_dates_are_accepted(self):
        body = {**self.sample, 'start_date': None, 'end_date': None}
        response = self.client.post(self.create_url(), body, format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def test_end_before_start_is_400_under_end_date(self):
        body = {**self.sample, 'start_date': '2026-06-01', 'end_date': '2026-05-31'}
        response = self.client.post(self.create_url(), body, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('end_date', response.data['errors'])

    def test_same_day_start_and_end_is_fine(self):
        body = {**self.sample, 'start_date': '2026-06-01', 'end_date': '2026-06-01'}
        response = self.client.post(self.create_url(), body, format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def test_agent_and_policy_type_are_required(self):
        response = self.client.post(self.create_url(), {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('agent', response.data['errors'])
        self.assertIn('policy_type', response.data['errors'])

    def test_unknown_agent_and_policy_type_are_400(self):
        unknown = '00000000-0000-0000-0000-000000000000'
        response = self.client.post(self.create_url(), {**self.sample, 'agent': unknown}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('agent', response.data['errors'])
        response = self.client.post(self.create_url(), {**self.sample, 'policy_type': unknown}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('policy_type', response.data['errors'])

    def test_duplicate_pair_is_400_under_policy_type(self):
        make_certification(self.agent, self.policy_type)
        response = self.client.post(self.create_url(), self.sample, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data['errors'], {'policy_type': ['Maria Alva is already certified for Medicare Advantage.']}
        )

    def test_deleted_pair_can_be_added_again(self):
        make_certification(self.agent, self.policy_type).delete()
        response = self.client.post(self.create_url(), self.sample, format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def test_other_agent_same_type_is_fine(self):
        make_certification(make_agent(name='Jim Carter', npn='2222'), self.policy_type)
        response = self.client.post(self.create_url(), self.sample, format='json')
        self.assertEqual(response.status_code, 201, response.data)


class CertificationListTests(CertificationAPITestCase):
    def test_lists_by_policy_type_then_agent_with_filters(self):
        jim = make_agent(name='Jim Carter', npn='2222')
        dental = make_policy_type(name='Dental')
        make_certification(self.agent, self.policy_type)
        make_certification(jim, self.policy_type)
        make_certification(jim, dental)

        response = self.client.get(self.list_url())
        self.assertEqual(response.status_code, 200)
        rows = [(c['policy_type']['name'], c['agent']['name']) for c in response.data['data']]
        self.assertEqual(
            rows,
            [('Dental', 'Jim Carter'), ('Medicare Advantage', 'Jim Carter'), ('Medicare Advantage', 'Maria Alva')],
        )
        self.assertEqual(response.data['meta']['total_items'], 3)

        response = self.client.get(self.list_url(), {'agent': str(jim.pk)})
        self.assertEqual([c['policy_type']['name'] for c in response.data['data']], ['Dental', 'Medicare Advantage'])

        response = self.client.get(self.list_url(), {'policy_type': str(dental.pk)})
        self.assertEqual([c['agent']['name'] for c in response.data['data']], ['Jim Carter'])

    def test_bad_agent_filter_is_400(self):
        response = self.client.get(self.list_url(), {'agent': 'not-a-uuid'})
        self.assertEqual(response.status_code, 400)

    def test_hides_deleted_certifications(self):
        make_certification(self.agent, self.policy_type).delete()
        response = self.client.get(self.list_url())
        self.assertEqual(response.data['data'], [])


class CertificationDetailTests(CertificationAPITestCase):
    def test_get(self):
        certification = make_certification(self.agent, self.policy_type)
        response = self.client.get(self.detail_url(certification))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['agent']['id'], str(self.agent.pk))

    def test_patch_updates_fields_and_records_note(self):
        certification = make_certification(self.agent, self.policy_type, start_date='2026-01-01')
        dental = make_policy_type(name='Dental')
        response = self.client.patch(
            self.detail_url(certification),
            {'policy_type': str(dental.pk), 'start_date': '2026-02-01', 'end_date': '2027-01-31', 'is_active': False},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data['data']
        self.assertEqual(data['policy_type']['name'], 'Dental')
        self.assertEqual(data['start_date'], '2026-02-01')
        self.assertFalse(data['is_active'])
        note = certification.notes.get()
        self.assertEqual(note.kind, 'edited')
        self.assertEqual(
            note.changes,
            [
                {'field': 'policy_type', 'from': 'Medicare Advantage', 'to': 'Dental'},
                {'field': 'start_date', 'from': '2026-01-01', 'to': '2026-02-01'},
                {'field': 'end_date', 'from': '', 'to': '2027-01-31'},
                {'field': 'status', 'from': 'active', 'to': 'inactive'},
            ],
        )

    def test_patch_can_clear_a_date(self):
        certification = make_certification(self.agent, self.policy_type, start_date='2026-01-01', end_date='2026-12-31')
        response = self.client.patch(self.detail_url(certification), {'end_date': None}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.data['data']['end_date'])
        self.assertEqual(certification.notes.get().changes, [{'field': 'end_date', 'from': '2026-12-31', 'to': ''}])

    def test_patch_with_no_change_writes_no_note(self):
        certification = make_certification(self.agent, self.policy_type, start_date='2026-01-01')
        response = self.client.patch(self.detail_url(certification), {'start_date': '2026-01-01'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(certification.notes.exists())

    def test_patch_checks_dates_against_stored_ones(self):
        certification = make_certification(self.agent, self.policy_type, start_date='2026-06-01')
        response = self.client.patch(self.detail_url(certification), {'end_date': '2026-05-01'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('end_date', response.data['errors'])

    def test_patch_duplicate_reported_under_the_side_that_was_sent(self):
        jim = make_agent(name='Jim Carter', npn='2222')
        dental = make_policy_type(name='Dental')
        make_certification(self.agent, self.policy_type)  # Maria / MA
        make_certification(jim, dental)  # Jim / Dental
        certification = make_certification(self.agent, dental)  # Maria / Dental

        # Changing the policy type to MA collides with Maria / MA: under policy_type.
        response = self.client.patch(self.detail_url(certification), {'policy_type': str(self.policy_type.pk)}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(response.data['errors']), ['policy_type'])

        # Changing the agent to Jim collides with Jim / Dental: under agent.
        response = self.client.patch(self.detail_url(certification), {'agent': str(jim.pk)}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(response.data['errors']), ['agent'])

    def test_patch_keeps_own_pair(self):
        certification = make_certification(self.agent, self.policy_type)
        response = self.client.patch(
            self.detail_url(certification),
            {'agent': str(self.agent.pk), 'policy_type': str(self.policy_type.pk)},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)

    def test_delete_is_soft(self):
        certification = make_certification(self.agent, self.policy_type)
        response = self.client.delete(self.detail_url(certification))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Certification.objects.filter(pk=certification.pk).exists())
        self.assertTrue(Certification.all_objects.filter(pk=certification.pk).exists())
        self.assertEqual(self.client.get(self.detail_url(certification)).status_code, 404)

    def test_notes_newest_first(self):
        certification = make_certification(self.agent, self.policy_type)
        self.client.patch(self.detail_url(certification), {'start_date': '2026-01-01'}, format='json')
        self.client.patch(self.detail_url(certification), {'start_date': '2026-02-01'}, format='json')
        response = self.client.get(self.notes_url(certification))
        self.assertEqual(response.status_code, 200)
        notes = response.data['data']
        self.assertEqual(len(notes), 2)
        self.assertEqual(notes[0]['changes'], [{'field': 'start_date', 'from': '2026-01-01', 'to': '2026-02-01'}])
        self.assertEqual(notes[0]['created_by'], 'Admin')


class CertificationPermissionTests(CertificationAPITestCase):
    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_user(email='staff@example.com', password='Sup3r-secret!', full_name='Staff')
        self.client.force_authenticate(self.staff)

    def test_anonymous_gets_401(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.list_url()).status_code, 401)

    def test_no_role_gets_403(self):
        self.assertEqual(self.client.get(self.list_url()).status_code, 403)

    def test_view_only_role_can_list_but_not_create(self):
        self.staff.role = make_role('certifications', can_view=True)
        self.staff.save()
        self.assertEqual(self.client.get(self.list_url()).status_code, 200)
        self.assertEqual(self.client.post(self.create_url(), self.sample, format='json').status_code, 403)

    def test_create_role_can_create(self):
        self.staff.role = make_role('certifications', can_view=True, can_create=True)
        self.staff.save()
        self.assertEqual(self.client.post(self.create_url(), self.sample, format='json').status_code, 201)

    def test_agents_or_policy_types_role_alone_is_not_enough(self):
        for module in ('agents', 'policy_types'):
            self.staff.role = make_role(module, can_view=True, can_create=True)
            self.staff.save()
            self.assertEqual(self.client.get(self.list_url()).status_code, 403, module)

    def test_module_is_listed_for_roles(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse('accounts:apis:roles:modules'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('certifications', str(response.data))


def make_pdf(name='certificate.pdf', body=b'%PDF-1.7\n%fake\n'):
    return SimpleUploadedFile(name, body, content_type='application/pdf')


class CertificationFileTests(CertificationAPITestCase):
    def setUp(self):
        super().setUp()
        self.media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        settings_override = override_settings(PRIVATE_MEDIA_ROOT=self.media_root)
        settings_override.enable()
        self.addCleanup(settings_override.disable)

    def create_with_file(self, **extra):
        body = {**self.sample, 'file': make_pdf(), **extra}
        return self.client.post(self.create_url(), body, format='multipart')

    def test_create_with_pdf_keeps_name_and_leaves_unverified(self):
        response = self.create_with_file()
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data['data']
        self.assertEqual(data['file_name'], 'certificate.pdf')
        self.assertFalse(data['is_verified'])
        self.assertNotIn('file', data)
        certification = Certification.objects.get(pk=data['id'])
        self.assertTrue(certification.file.name.startswith('certifications/'))
        self.assertNotIn('certificate', certification.file.name)
        note = certification.notes.get()
        self.assertEqual(note.changes[-1], {'field': 'file', 'from': '', 'to': 'certificate.pdf'})

    def test_is_verified_is_stored_and_noted_as_yes_no(self):
        response = self.create_with_file(is_verified='true')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data['data']['is_verified'])
        certification = Certification.objects.get(pk=response.data['data']['id'])
        fields = [change['field'] for change in certification.notes.get().changes]
        self.assertEqual(fields, ['agent', 'policy_type', 'start_date', 'end_date', 'is_verified', 'status', 'file'])
        response = self.client.patch(self.detail_url(certification), {'is_verified': False}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(certification.notes.first().changes, [{'field': 'is_verified', 'from': 'yes', 'to': 'no'}])

    def test_without_a_file_name_is_null_and_download_is_404(self):
        response = self.client.post(self.create_url(), self.sample, format='json')
        self.assertIsNone(response.data['data']['file_name'])
        certification = Certification.objects.get(pk=response.data['data']['id'])
        self.assertEqual(self.client.get(self.file_url(certification)).status_code, 404)

    def test_non_pdf_is_400_under_file(self):
        for upload in (
            SimpleUploadedFile('notes.txt', b'hello', content_type='text/plain'),
            SimpleUploadedFile('fake.pdf', b'not a pdf', content_type='application/pdf'),
        ):
            response = self.client.post(self.create_url(), {**self.sample, 'file': upload}, format='multipart')
            self.assertEqual(response.status_code, 400, upload.name)
            self.assertIn('file', response.data['errors'])
        self.assertFalse(Certification.objects.exists())

    def test_file_over_10_mb_is_400_under_file(self):
        big = make_pdf(body=b'%PDF-' + b'0' * (10 * 1024 * 1024))
        response = self.client.post(self.create_url(), {**self.sample, 'file': big}, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertIn('file', response.data['errors'])

    def test_download_returns_the_pdf_under_its_name(self):
        certification = Certification.objects.get(pk=self.create_with_file().data['data']['id'])
        response = self.client.get(self.file_url(certification))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('certificate.pdf', response['Content-Disposition'])
        self.assertEqual(b''.join(response.streaming_content), b'%PDF-1.7\n%fake\n')

    def test_new_upload_replaces_file_and_notes_both_names(self):
        certification = Certification.objects.get(pk=self.create_with_file().data['data']['id'])
        old_name = certification.file.name
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(
                self.detail_url(certification),
                {'file': make_pdf('renewed.pdf')},
                format='multipart',
            )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['file_name'], 'renewed.pdf')
        certification.refresh_from_db()
        self.assertNotEqual(certification.file.name, old_name)
        self.assertFalse(certification.file.storage.exists(old_name))
        self.assertTrue(certification.file.storage.exists(certification.file.name))
        self.assertEqual(
            certification.notes.first().changes,
            [{'field': 'file', 'from': 'certificate.pdf', 'to': 'renewed.pdf'}],
        )

    def test_patch_without_file_keeps_it(self):
        certification = Certification.objects.get(pk=self.create_with_file().data['data']['id'])
        response = self.client.patch(
            self.detail_url(certification), {'end_date': '', 'is_verified': 'true'}, format='multipart'
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['file_name'], 'certificate.pdf')
        self.assertIsNone(response.data['data']['end_date'])
        self.assertTrue(response.data['data']['is_verified'])

    def test_download_needs_certifications_view(self):
        certification = Certification.objects.get(pk=self.create_with_file().data['data']['id'])
        staff = User.objects.create_user(email='staff@example.com', password='Sup3r-secret!', full_name='Staff')
        self.client.force_authenticate(staff)
        self.assertEqual(self.client.get(self.file_url(certification)).status_code, 403)
        staff.role = make_role('certifications', can_view=True)
        staff.save()
        self.client.force_authenticate(User.objects.get(pk=staff.pk))
        self.assertEqual(self.client.get(self.file_url(certification)).status_code, 200)
