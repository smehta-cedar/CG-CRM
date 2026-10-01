import datetime
import io
import shutil
import tempfile
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Role, RolePermission, User
from apps.agents.models import Agent
from apps.carriers.models import Carrier

from .models import Certification, CertificationNote
from .utils import add_contract_certifications, certification_due_date


def make_agent(name='Maria Alva', npn='17654321', **overrides):
    return Agent.objects.create(name=name, npn=npn, **overrides)


def make_carrier(name='Humana', lines=('MAPD',), **overrides):
    return Carrier.objects.create(name=name, lines_of_business=list(lines), **overrides)


def make_certification(agent, carrier=None, line_of_business='', **overrides):
    return Certification.objects.create(agent=agent, carrier=carrier, line_of_business=line_of_business, **overrides)


def make_role(module, **flags):
    role = Role.objects.create(name=f"{module}-{'-'.join(k for k, v in flags.items() if v) or 'none'}")
    RolePermission.objects.create(role=role, module=module, **flags)
    return role


class CertificationDueDateTests(SimpleTestCase):
    def test_next_deadline_on_or_after_today(self):
        self.assertEqual(certification_due_date(datetime.date(2026, 3, 1)), datetime.date(2026, 9, 15))
        self.assertEqual(certification_due_date(datetime.date(2026, 9, 15)), datetime.date(2026, 9, 15))
        self.assertEqual(certification_due_date(datetime.date(2026, 10, 1)), datetime.date(2027, 9, 15))

    @override_settings(CERTIFICATION_DUE_MONTH=12, CERTIFICATION_DUE_DAY=31)
    def test_deadline_comes_from_settings(self):
        self.assertEqual(certification_due_date(datetime.date(2026, 10, 1)), datetime.date(2026, 12, 31))


class CertificationAPITestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='Sup3r-secret!', full_name='Admin')
        self.client.force_authenticate(self.admin)
        self.agent = make_agent()
        self.humana = make_carrier()
        self.sample = {
            'agent': str(self.agent.pk),
            'carrier': str(self.humana.pk),
            'line_of_business': 'MAPD',
            'due_date': '2027-09-15',
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
        self.assertEqual(data['carrier']['name'], 'Humana')
        self.assertEqual(data['line_of_business'], 'MAPD')
        self.assertEqual(data['due_date'], '2027-09-15')
        self.assertEqual(data['start_date'], '2026-01-01')
        self.assertEqual(data['end_date'], '2026-12-31')
        self.assertNotIn('policy_type', data)
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
                {'field': 'carrier', 'from': '', 'to': 'Humana'},
                {'field': 'line_of_business', 'from': '', 'to': 'MAPD'},
                {'field': 'due_date', 'from': '', 'to': '2027-09-15'},
                {'field': 'start_date', 'from': '', 'to': '2026-01-01'},
                {'field': 'end_date', 'from': '', 'to': '2026-12-31'},
                {'field': 'is_verified', 'from': '', 'to': 'no'},
                {'field': 'status', 'from': '', 'to': 'active'},
            ],
        )

    def test_only_agent_is_required(self):
        response = self.client.post(self.create_url(), {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(response.data['errors']), ['agent'])

        with mock.patch('apps.policies.utils.timezone.localdate', return_value=datetime.date(2026, 10, 1)):
            response = self.client.post(self.create_url(), {'agent': str(self.agent.pk)}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data['data']
        self.assertIsNone(data['carrier'])
        self.assertEqual(data['line_of_business'], '')
        self.assertIsNone(data['start_date'])
        # The due date defaults to the next deadline.
        self.assertEqual(data['due_date'], '2027-09-15')

    def test_dates_are_not_checked(self):
        body = {**self.sample, 'start_date': '2026-06-01', 'end_date': '2026-05-31'}
        response = self.client.post(self.create_url(), body, format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def test_the_same_certification_can_be_added_twice(self):
        self.assertEqual(self.client.post(self.create_url(), self.sample, format='json').status_code, 201)
        self.assertEqual(self.client.post(self.create_url(), self.sample, format='json').status_code, 201)
        self.assertEqual(Certification.objects.filter(agent=self.agent).count(), 2)

    def test_any_line_and_carrier_go_together(self):
        # The line need not be one the carrier writes.
        response = self.client.post(self.create_url(), {**self.sample, 'line_of_business': 'Life'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def test_unknown_line_agent_or_carrier_is_400(self):
        unknown = '00000000-0000-0000-0000-000000000000'
        for field, value in (('line_of_business', 'Dental'), ('agent', unknown), ('carrier', unknown)):
            response = self.client.post(self.create_url(), {**self.sample, field: value}, format='json')
            self.assertEqual(response.status_code, 400, field)
            self.assertIn(field, response.data['errors'])


class CertificationListTests(CertificationAPITestCase):
    def test_lists_by_agent_then_due_date_with_filters(self):
        jim = make_agent(name='Jim Carter', npn='2222')
        aetna = make_carrier(name='Aetna', lines=['MAPD', 'Life'])
        make_certification(self.agent, self.humana, 'MAPD', due_date='2027-09-15')
        make_certification(jim, self.humana, 'MAPD', due_date='2027-09-15')
        make_certification(jim, aetna, 'Life', due_date='2026-09-15')

        response = self.client.get(self.list_url())
        self.assertEqual(response.status_code, 200)
        rows = [(c['agent']['name'], c['carrier']['name'], c['line_of_business']) for c in response.data['data']]
        self.assertEqual(
            rows,
            [('Jim Carter', 'Aetna', 'Life'), ('Jim Carter', 'Humana', 'MAPD'), ('Maria Alva', 'Humana', 'MAPD')],
        )
        self.assertEqual(response.data['meta']['total_items'], 3)

        response = self.client.get(self.list_url(), {'agent': str(jim.pk)})
        self.assertEqual(len(response.data['data']), 2)
        response = self.client.get(self.list_url(), {'carrier': str(self.humana.pk)})
        self.assertEqual([c['agent']['name'] for c in response.data['data']], ['Jim Carter', 'Maria Alva'])
        response = self.client.get(self.list_url(), {'line_of_business': 'Life'})
        self.assertEqual([c['carrier']['name'] for c in response.data['data']], ['Aetna'])

    def test_bad_agent_filter_is_400(self):
        response = self.client.get(self.list_url(), {'agent': 'not-a-uuid'})
        self.assertEqual(response.status_code, 400)

    def test_hides_deleted_certifications(self):
        make_certification(self.agent).delete()
        response = self.client.get(self.list_url())
        self.assertEqual(response.data['data'], [])


class CertificationDetailTests(CertificationAPITestCase):
    def test_get(self):
        certification = make_certification(self.agent, self.humana, 'MAPD')
        response = self.client.get(self.detail_url(certification))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['agent']['id'], str(self.agent.pk))
        self.assertEqual(response.data['data']['carrier']['id'], str(self.humana.pk))

    def test_patch_updates_fields_and_records_note(self):
        certification = make_certification(self.agent, self.humana, 'MAPD', start_date='2026-01-01')
        aetna = make_carrier(name='Aetna', lines=['Life'])
        response = self.client.patch(
            self.detail_url(certification),
            {
                'carrier': str(aetna.pk),
                'line_of_business': 'Life',
                'due_date': '2027-09-15',
                'start_date': '2026-02-01',
                'is_active': False,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data['data']
        self.assertEqual(data['carrier']['name'], 'Aetna')
        self.assertEqual(data['line_of_business'], 'Life')
        self.assertFalse(data['is_active'])
        note = certification.notes.get()
        self.assertEqual(note.kind, 'edited')
        self.assertEqual(
            note.changes,
            [
                {'field': 'carrier', 'from': 'Humana', 'to': 'Aetna'},
                {'field': 'line_of_business', 'from': 'MAPD', 'to': 'Life'},
                {'field': 'due_date', 'from': '', 'to': '2027-09-15'},
                {'field': 'start_date', 'from': '2026-01-01', 'to': '2026-02-01'},
                {'field': 'status', 'from': 'active', 'to': 'inactive'},
            ],
        )

    def test_patch_can_clear_carrier_line_and_dates(self):
        certification = make_certification(self.agent, self.humana, 'MAPD', end_date='2026-12-31')
        response = self.client.patch(
            self.detail_url(certification),
            {'carrier': None, 'line_of_business': '', 'end_date': None},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data['data']
        self.assertIsNone(data['carrier'])
        self.assertEqual(data['line_of_business'], '')
        self.assertIsNone(data['end_date'])

    def test_patch_with_no_change_writes_no_note(self):
        certification = make_certification(self.agent, start_date='2026-01-01')
        response = self.client.patch(self.detail_url(certification), {'start_date': '2026-01-01'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(certification.notes.exists())

    def test_patch_dates_are_not_checked(self):
        certification = make_certification(self.agent, start_date='2026-06-01')
        response = self.client.patch(self.detail_url(certification), {'end_date': '2026-05-01'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)

    def test_delete_is_soft(self):
        certification = make_certification(self.agent)
        response = self.client.delete(self.detail_url(certification))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Certification.objects.filter(pk=certification.pk).exists())
        self.assertTrue(Certification.all_objects.filter(pk=certification.pk).exists())
        self.assertEqual(self.client.get(self.detail_url(certification)).status_code, 404)

    def test_notes_newest_first(self):
        certification = make_certification(self.agent)
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
        self.assertEqual(
            fields,
            ['agent', 'carrier', 'line_of_business', 'due_date', 'start_date', 'end_date', 'is_verified', 'status', 'file'],
        )
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

    def test_multipart_carries_carrier_and_line(self):
        response = self.create_with_file(line_of_business='Life')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['data']['carrier']['name'], 'Humana')
        self.assertEqual(response.data['data']['line_of_business'], 'Life')
        self.assertEqual(response.data['data']['file_name'], 'certificate.pdf')

    def test_download_needs_certifications_view(self):
        certification = Certification.objects.get(pk=self.create_with_file().data['data']['id'])
        staff = User.objects.create_user(email='staff@example.com', password='Sup3r-secret!', full_name='Staff')
        self.client.force_authenticate(staff)
        self.assertEqual(self.client.get(self.file_url(certification)).status_code, 403)
        staff.role = make_role('certifications', can_view=True)
        staff.save()
        self.client.force_authenticate(User.objects.get(pk=staff.pk))
        self.assertEqual(self.client.get(self.file_url(certification)).status_code, 200)


class ContractCertificationTests(CertificationAPITestCase):
    DUE = datetime.date(2027, 9, 15)

    def setUp(self):
        super().setUp()
        self.humana.lines_of_business = ['Medicare Supplement', 'MAPD']
        self.humana.save()

    def lines(self, **filters):
        rows = Certification.objects.filter(agent=self.agent, carrier=self.humana, **filters)
        return sorted(row.line_of_business for row in rows)

    def test_adds_one_row_per_line_and_skips_covered_ones(self):
        make_certification(self.agent, self.humana, 'MAPD', due_date=self.DUE)
        touched = add_contract_certifications(self.agent, self.humana, due_date=self.DUE)
        self.assertEqual([row.line_of_business for row in touched], ['Medicare Supplement'])
        self.assertEqual(self.lines(), ['MAPD', 'Medicare Supplement'])
        # Running again adds nothing.
        self.assertEqual(add_contract_certifications(self.agent, self.humana, due_date=self.DUE), [])

    def test_last_years_rows_do_not_count(self):
        make_certification(self.agent, self.humana, 'MAPD', due_date=datetime.date(2026, 9, 15))
        add_contract_certifications(self.agent, self.humana, due_date=self.DUE)
        self.assertEqual(self.lines(due_date=self.DUE), ['MAPD', 'Medicare Supplement'])

    def test_fills_in_a_row_with_the_carrier_but_no_line(self):
        old = make_certification(self.agent, self.humana)
        add_contract_certifications(self.agent, self.humana, due_date=self.DUE)
        old.refresh_from_db()
        self.assertEqual((old.line_of_business, old.due_date), ('Medicare Supplement', self.DUE))
        self.assertEqual(old.notes.get().kind, 'edited')
        self.assertEqual(self.lines(), ['MAPD', 'Medicare Supplement'])

    def test_an_undated_row_with_a_line_counts_and_takes_the_date(self):
        old = make_certification(self.agent, self.humana, 'MAPD')
        touched = add_contract_certifications(self.agent, self.humana, due_date=self.DUE)
        self.assertEqual(len(touched), 2)
        old.refresh_from_db()
        self.assertEqual(old.due_date, self.DUE)
        self.assertEqual(self.lines(), ['MAPD', 'Medicare Supplement'])

    def test_command_covers_every_contract_and_dates_the_rest(self):
        from django.core.management import call_command

        from apps.contracts.models import CarrierContract

        CarrierContract.objects.create(agent=self.agent, carrier=self.humana)
        loose = make_certification(make_agent(name='Jim Carter', npn='2222'))
        call_command('add_contract_certifications', due='2027-09-15', stdout=io.StringIO())
        self.assertEqual(self.lines(due_date=self.DUE), ['MAPD', 'Medicare Supplement'])
        loose.refresh_from_db()
        self.assertEqual(loose.due_date, self.DUE)
        # A second run changes nothing.
        call_command('add_contract_certifications', due='2027-09-15', stdout=io.StringIO())
        self.assertEqual(Certification.objects.filter(agent=self.agent).count(), 2)
