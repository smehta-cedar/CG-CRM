from datetime import date

from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Role, RolePermission, User

from .models import Agency, AgencyNote, State

SAMPLE = {
    'name': 'Cedar Grove Senior Health Solutions',
    'aliases': ['Cedar Grove', 'CGSHS'],
    'npn': '20987654',
    'email': 'office@example.com',
    'phone': '(555)010-1000',
}


def make_agency(**overrides):
    return Agency.objects.create(**{**SAMPLE, **overrides})


def default_term():
    """The dates a new licence row gets when none are sent: today, two years on."""
    today = date.today()
    return today, today.replace(year=today.year + 2)


def make_role(**flags):
    role = Role.objects.create(name=f"agencies-{'-'.join(k for k, v in flags.items() if v) or 'none'}")
    RolePermission.objects.create(role=role, module='agencies', **flags)
    return role


class AgencyAPITestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='Sup3r-secret!', full_name='Admin')
        self.client.force_authenticate(self.admin)

    def list_url(self):
        return reverse('agency:apis:agencies:list')

    def create_url(self):
        return reverse('agency:apis:agencies:create')

    def detail_url(self, agency):
        return reverse('agency:apis:agencies:detail', args=[agency.pk])


class AgencyCreateTests(AgencyAPITestCase):
    def test_creates_agency_from_sample(self):
        response = self.client.post(self.create_url(), SAMPLE, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data['data']
        self.assertEqual(data['name'], SAMPLE['name'])
        self.assertEqual(data['aliases'], SAMPLE['aliases'])
        self.assertTrue(data['is_active'])
        self.assertEqual(data['npn'], SAMPLE['npn'])
        agency = Agency.objects.get(pk=data['id'])
        self.assertEqual(agency.created_by, self.admin)

    def test_only_name_is_required(self):
        response = self.client.post(self.create_url(), {'name': 'Solo Agency'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data['data']
        self.assertEqual(data['aliases'], [])
        self.assertTrue(data['is_active'])
        self.assertEqual(data['npn'], '')

    def test_name_is_required(self):
        response = self.client.post(self.create_url(), {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('name', response.data['errors'])

    def test_rejects_duplicate_name_case_insensitively(self):
        make_agency()
        response = self.client.post(
            self.create_url(), {'name': SAMPLE['name'].upper(), 'npn': '1'}, format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('name', response.data['errors'])

    def test_rejects_duplicate_npn(self):
        make_agency()
        response = self.client.post(self.create_url(), {'name': 'Other', 'npn': SAMPLE['npn']}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('npn', response.data['errors'])

    def test_blank_npn_is_not_unique(self):
        make_agency(npn='')
        response = self.client.post(self.create_url(), {'name': 'Other', 'npn': ''}, format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def test_rejects_non_numeric_npn(self):
        response = self.client.post(self.create_url(), {'name': 'Other', 'npn': 'AB123'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('npn', response.data['errors'])

    def test_rejects_non_boolean_is_active(self):
        response = self.client.post(self.create_url(), {'name': 'Other', 'is_active': 'paused'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('is_active', response.data['errors'])

    def test_aliases_are_trimmed_and_deduplicated(self):
        response = self.client.post(
            self.create_url(),
            {'name': 'Other', 'aliases': ['  Cedar  Grove ', 'cedar grove', '', 'CGSHS']},
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['data']['aliases'], ['Cedar Grove', 'CGSHS'])

    def test_deleted_agency_name_and_npn_can_be_reused(self):
        agency = make_agency()
        agency.delete()
        response = self.client.post(self.create_url(), SAMPLE, format='json')
        self.assertEqual(response.status_code, 201, response.data)


class AgencyListTests(AgencyAPITestCase):
    def test_lists_agencies_with_pagination_meta(self):
        make_agency()
        make_agency(name='Second', npn='2', is_active=False)
        response = self.client.get(self.list_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['meta']['total_items'], 2)
        self.assertEqual(len(response.data['data']), 2)

    def test_hides_deleted_agencies(self):
        make_agency().delete()
        response = self.client.get(self.list_url())
        self.assertEqual(response.data['meta']['total_items'], 0)

    def test_search_matches_alias(self):
        make_agency()
        make_agency(name='Second', npn='2', aliases=[])
        response = self.client.get(self.list_url(), {'search': 'cgshs'})
        self.assertEqual([a['name'] for a in response.data['data']], [SAMPLE['name']])

    def test_search_matches_npn(self):
        make_agency()
        make_agency(name='Second', npn='2')
        response = self.client.get(self.list_url(), {'search': '2098'})
        self.assertEqual([a['name'] for a in response.data['data']], [SAMPLE['name']])

    def test_filters_by_is_active(self):
        make_agency()
        make_agency(name='Second', npn='2', is_active=False)
        response = self.client.get(self.list_url(), {'is_active': 'false'})
        self.assertEqual([a['name'] for a in response.data['data']], ['Second'])

    def test_rejects_non_boolean_is_active_filter(self):
        response = self.client.get(self.list_url(), {'is_active': 'paused'})
        self.assertEqual(response.status_code, 400)


class AgencyDetailTests(AgencyAPITestCase):
    def test_gets_agency(self):
        agency = make_agency()
        response = self.client.get(self.detail_url(agency))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['id'], str(agency.pk))

    def test_unknown_agency_is_404(self):
        agency = make_agency()
        agency.delete()
        response = self.client.get(self.detail_url(agency))
        self.assertEqual(response.status_code, 404)

    def test_patch_updates_only_sent_fields(self):
        agency = make_agency()
        response = self.client.patch(self.detail_url(agency), {'is_active': False, 'phone': '555'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        agency.refresh_from_db()
        self.assertFalse(agency.is_active)
        self.assertEqual(agency.phone, '555')
        self.assertEqual(agency.name, SAMPLE['name'])
        self.assertEqual(agency.aliases, SAMPLE['aliases'])
        self.assertEqual(agency.updated_by, self.admin)

    def test_patch_can_change_case_of_own_name(self):
        agency = make_agency()
        response = self.client.patch(self.detail_url(agency), {'name': SAMPLE['name'].upper()}, format='json')
        self.assertEqual(response.status_code, 200, response.data)

    def test_patch_rejects_name_taken_by_another_agency(self):
        make_agency()
        other = make_agency(name='Other', npn='2')
        response = self.client.patch(self.detail_url(other), {'name': SAMPLE['name']}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('name', response.data['errors'])

    def test_patch_rejects_npn_taken_by_another_agency(self):
        make_agency()
        other = make_agency(name='Other', npn='2')
        response = self.client.patch(self.detail_url(other), {'npn': SAMPLE['npn']}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('npn', response.data['errors'])

    def test_patch_can_clear_aliases(self):
        agency = make_agency()
        response = self.client.patch(self.detail_url(agency), {'aliases': []}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['aliases'], [])

    def test_delete_is_soft(self):
        agency = make_agency()
        response = self.client.delete(self.detail_url(agency))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Agency.objects.filter(pk=agency.pk).exists())
        deleted = Agency.all_objects.get(pk=agency.pk)
        self.assertTrue(deleted.is_deleted)
        self.assertEqual(deleted.deleted_by, self.admin)


class AgencyPermissionTests(AgencyAPITestCase):
    def test_anonymous_is_401(self):
        self.client.force_authenticate(None)
        response = self.client.get(self.list_url())
        self.assertEqual(response.status_code, 401)

    def test_role_without_module_is_403(self):
        user = User.objects.create_user(email='nobody@example.com', password='Sup3r-secret!', full_name='Nobody')
        self.client.force_authenticate(user)
        response = self.client.get(self.list_url())
        self.assertEqual(response.status_code, 403)

    def test_view_only_role_can_list_but_not_create(self):
        role = make_role(can_view=True)
        user = User.objects.create_user(
            email='viewer@example.com', password='Sup3r-secret!', full_name='Viewer'
        )
        user.roles.add(role)
        self.client.force_authenticate(user)
        self.assertEqual(self.client.get(self.list_url()).status_code, 200)
        self.assertEqual(self.client.post(self.create_url(), {'name': 'X'}, format='json').status_code, 403)

    def test_delete_needs_delete_permission(self):
        agency = make_agency()
        role = make_role(can_view=True, can_update=True)
        user = User.objects.create_user(
            email='editor@example.com', password='Sup3r-secret!', full_name='Editor'
        )
        user.roles.add(role)
        self.client.force_authenticate(user)
        self.assertEqual(self.client.patch(self.detail_url(agency), {'phone': '1'}, format='json').status_code, 200)
        self.assertEqual(self.client.delete(self.detail_url(agency)).status_code, 403)


class StateModelTests(APITestCase):
    def test_seed_loads_every_state(self):
        from .models import State
        from .models.states import US_STATES

        self.assertEqual(State.objects.count(), len(US_STATES))
        self.assertEqual(State.objects.get(code='CA').name, 'California')
        self.assertEqual(State.objects.get(code='CA').search_key, 'california,ca')

    def test_states_are_ordered_by_name(self):
        from .models import State

        names = list(State.objects.values_list('name', flat=True))
        self.assertEqual(names, sorted(names))

    def test_save_normalizes_code_and_search_key(self):
        from .models import State

        state = State.objects.create(
            name='  Puerto   Rico ',
            code=' pr ',
            search_key=' Puerto Rico, PR ,pr,, boricua ',
        )
        self.assertEqual(state.name, 'Puerto Rico')
        self.assertEqual(state.code, 'PR')
        self.assertEqual(state.search_key, 'puerto rico,pr,boricua')
        self.assertEqual(state.search_terms, ['puerto rico', 'pr', 'boricua'])

    def test_code_is_unique_case_insensitively(self):
        from django.db import IntegrityError

        from .models import State

        with self.assertRaises(IntegrityError):
            State.objects.create(name='Other', code='ca')

    def test_name_is_unique_case_insensitively(self):
        from django.db import IntegrityError

        from .models import State

        with self.assertRaises(IntegrityError):
            State.objects.create(name='CALIFORNIA', code='ZZ')

    def test_deleted_state_frees_its_code(self):
        from .models import State

        State.objects.get(code='CA').delete()
        State.objects.create(name='California Again', code='CA')


class AgencyLicenseTests(AgencyAPITestCase):
    def test_create_with_licenses_records_note(self):
        response = self.client.post(
            self.create_url(),
            {**SAMPLE, 'licenses': [{'state': 'TX', 'license_number': '2450019'}, {'state': 'FL', 'license_number': 'L127733'}]},
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        rows = response.data['data']['licenses']
        self.assertEqual([(row['state'], row['license_number'], row['status']) for row in rows], [('FL', 'L127733', 'active'), ('TX', '2450019', 'active')])
        note = AgencyNote.objects.get(agency_id=response.data['data']['id'])
        by_field = {change['field']: change['to'] for change in note.changes}
        self.assertEqual(by_field['licensed_states'], 'FL, TX')
        self.assertEqual(by_field['license_numbers'], 'FL L127733, TX 2450019')

    def test_patch_syncs_licenses_and_notes(self):
        agency = make_agency()
        agency.licenses.create(state=State.objects.get(code='TX'), license_number='1')
        response = self.client.patch(
            self.detail_url(agency),
            {'licenses': [{'state': 'TX', 'license_number': '2'}, {'state': 'GA', 'license_number': '3'}]},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([(row['state'], row['license_number']) for row in response.data['data']['licenses']], [('GA', '3'), ('TX', '2')])
        self.assertEqual(
            agency.notes.get().changes,
            [
                {'field': 'licensed_states', 'from': 'TX', 'to': 'GA, TX'},
                {'field': 'license_numbers', 'from': 'TX 1', 'to': 'GA 3, TX 2'},
                {'field': 'license_statuses', 'from': 'TX active', 'to': 'GA active, TX active'},
                {'field': 'license_dates', 'from': '', 'to': 'GA {} to {}'.format(*default_term())},
            ],
        )
        response = self.client.get(reverse('agency:apis:agencies:notes', args=[agency.pk]))
        self.assertEqual(len(response.data['data']), 1)

    def test_license_status_is_set_and_noted(self):
        agency = make_agency()
        agency.licenses.create(state=State.objects.get(code='TX'), license_number='1')
        response = self.client.patch(
            self.detail_url(agency),
            {'licenses': [{'state': 'TX', 'license_number': '1', 'status': 'expired'}, {'state': 'GA', 'license_number': '3', 'status': 'applied'}]},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([(row['state'], row['status']) for row in response.data['data']['licenses']], [('GA', 'applied'), ('TX', 'expired')])
        self.assertEqual(
            agency.notes.get().changes,
            [
                {'field': 'licensed_states', 'from': 'TX', 'to': 'GA, TX'},
                {'field': 'license_numbers', 'from': 'TX 1', 'to': 'GA 3, TX 1'},
                {'field': 'license_statuses', 'from': 'TX active', 'to': 'GA applied, TX expired'},
                {'field': 'license_dates', 'from': '', 'to': 'GA {} to {}'.format(*default_term())},
            ],
        )

    def test_license_dates_are_set_kept_and_checked(self):
        agency = make_agency()
        agency.licenses.create(state=State.objects.get(code='TX'), license_number='1', start_date=date(2024, 1, 1), end_date=date(2026, 1, 1))
        response = self.client.patch(
            self.detail_url(agency),
            {'licenses': [{'state': 'TX', 'license_number': '1', 'end_date': '2027-01-01'}, {'state': 'GA', 'license_number': '3', 'start_date': '2025-05-05', 'end_date': '2027-05-05'}]},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        rows = {row['state']: row for row in response.data['data']['licenses']}
        self.assertEqual((rows['TX']['start_date'], rows['TX']['end_date']), ('2024-01-01', '2027-01-01'))
        self.assertEqual((rows['GA']['start_date'], rows['GA']['end_date']), ('2025-05-05', '2027-05-05'))
        self.assertIn(
            {'field': 'license_dates', 'from': 'TX 2024-01-01 to 2026-01-01', 'to': 'GA 2025-05-05 to 2027-05-05, TX 2024-01-01 to 2027-01-01'},
            agency.notes.get().changes,
        )
        response = self.client.patch(
            self.detail_url(agency),
            {'licenses': [{'state': 'TX', 'start_date': '2027-01-01', 'end_date': '2026-01-01'}]},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('licenses', response.data['errors'])

    def test_license_status_left_out_keeps_the_row_status(self):
        agency = make_agency()
        agency.licenses.create(state=State.objects.get(code='TX'), license_number='1', status='cancelled')
        response = self.client.patch(self.detail_url(agency), {'licenses': [{'state': 'TX', 'license_number': '2'}]}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['licenses'][0]['status'], 'cancelled')
        self.assertEqual([change['field'] for change in agency.notes.get().changes], ['license_numbers'])

    def test_every_license_status_is_accepted(self):
        for status in ('active', 'pending', 'review', 'applied', 'expired', 'cancelled'):
            response = self.client.post(self.create_url(), {**SAMPLE, 'name': f'Agency {status}', 'npn': '', 'licenses': [{'state': 'TX', 'status': status}]}, format='json')
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response.data['data']['licenses'][0]['status'], status)

    def test_rejects_unknown_license_status(self):
        response = self.client.post(self.create_url(), {**SAMPLE, 'licenses': [{'state': 'TX', 'status': 'lapsed'}]}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('licenses', response.data['errors'])

    def test_rejects_unknown_license_state(self):
        response = self.client.post(self.create_url(), {**SAMPLE, 'licenses': [{'state': 'ZZ'}]}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('licenses', response.data['errors'])
