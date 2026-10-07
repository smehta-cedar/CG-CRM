from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Role, RolePermission, User
from apps.agency.models import State

from .models import Carrier, CarrierNote, CarrierStateLicense

SAMPLE = {
    'name': 'Humana',
    'aliases': ['Humana Inc'],
    'lines_of_business': ['MAPD'],
    'licenses': [{'state': 'FL'}, {'state': 'TX'}, {'state': 'LA'}],
}


def make_carrier(available_states=('FL', 'TX', 'LA'), **overrides):
    """A carrier with one blank active state row per code, like the API makes."""
    fields = {**SAMPLE, **overrides}
    fields.pop('licenses')
    carrier = Carrier.objects.create(**fields)
    states = list(State.objects.filter(code__in=available_states))
    for state in states:
        CarrierStateLicense.objects.create(carrier=carrier, state=state)
    carrier.available_states.set(states)
    return carrier


def make_role(**flags):
    role = Role.objects.create(name=f"carriers-{'-'.join(k for k, v in flags.items() if v) or 'none'}")
    RolePermission.objects.create(role=role, module='carriers', **flags)
    return role


class CarrierAPITestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='Sup3r-secret!', full_name='Admin')
        self.client.force_authenticate(self.admin)

    def list_url(self):
        return reverse('carriers:apis:carriers:list')

    def create_url(self):
        return reverse('carriers:apis:carriers:create')

    def detail_url(self, carrier):
        return reverse('carriers:apis:carriers:detail', args=[carrier.pk])

    def notes_url(self, carrier):
        return reverse('carriers:apis:carriers:notes', args=[carrier.pk])


class CarrierCreateTests(CarrierAPITestCase):
    def test_creates_carrier_from_sample(self):
        response = self.client.post(self.create_url(), SAMPLE, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data['data']
        self.assertEqual(data['name'], 'Humana')
        self.assertEqual(data['aliases'], ['Humana Inc'])
        self.assertEqual(data['lines_of_business'], ['MAPD'])
        # States come back in code order whatever order they were sent in.
        self.assertEqual(data['available_states'], ['FL', 'LA', 'TX'])
        self.assertEqual(data['link'], '')
        self.assertEqual(data['status'], 'active')
        self.assertTrue(data['is_active'])
        carrier = Carrier.objects.get(pk=data['id'])
        self.assertEqual(carrier.created_by, self.admin)

    def test_records_an_added_note(self):
        response = self.client.post(self.create_url(), SAMPLE, format='json')
        note = CarrierNote.objects.get(carrier_id=response.data['data']['id'])
        self.assertEqual(note.kind, 'added')
        self.assertEqual(note.created_by, self.admin)
        self.assertEqual(
            note.changes,
            [
                {'field': 'name', 'from': '', 'to': 'Humana'},
                {'field': 'aliases', 'from': '', 'to': 'Humana Inc'},
                {'field': 'lines_of_business', 'from': '', 'to': 'MAPD'},
                {'field': 'available_states', 'from': '', 'to': 'FL, LA, TX'},
                {'field': 'license_statuses', 'from': '', 'to': 'FL active, LA active, TX active'},
                {'field': 'status', 'from': '', 'to': 'active'},
            ],
        )

    def test_name_and_a_line_are_required(self):
        response = self.client.post(self.create_url(), {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('name', response.data['errors'])
        self.assertIn('lines_of_business', response.data['errors'])

        response = self.client.post(self.create_url(), {'name': 'Solo', 'lines_of_business': []}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('lines_of_business', response.data['errors'])

    def test_lines_keep_catalog_order_and_drop_duplicates(self):
        response = self.client.post(
            self.create_url(),
            {'name': 'Solo', 'lines_of_business': ['Life', 'MAPD', 'Life', 'Annuities']},
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['data']['lines_of_business'], ['MAPD', 'Life', 'Annuities'])

    def test_rejects_unknown_line(self):
        response = self.client.post(self.create_url(), {'name': 'Solo', 'lines_of_business': ['Dental']}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('lines_of_business', response.data['errors'])

    def test_rejects_old_supp_ancillary_line(self):
        response = self.client.post(
            self.create_url(), {'name': 'Solo', 'lines_of_business': ['Supp/Ancillary']}, format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('lines_of_business', response.data['errors'])

    def test_medicare_supplement_comes_before_ancillary(self):
        response = self.client.post(
            self.create_url(),
            {'name': 'Solo', 'lines_of_business': ['Ancillary', 'Medicare Supplement']},
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['data']['lines_of_business'], ['Medicare Supplement', 'Ancillary'])

    def test_rejects_general_line(self):
        response = self.client.post(self.create_url(), {'name': 'Solo', 'lines_of_business': ['General']}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('lines_of_business', response.data['errors'])

    def test_rejects_unknown_state(self):
        response = self.client.post(
            self.create_url(), {**SAMPLE, 'licenses': [{'state': 'TX'}, {'state': 'ZZ'}]}, format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('licenses', response.data['errors'])

    def test_rejects_duplicate_name_case_insensitively(self):
        make_carrier()
        response = self.client.post(self.create_url(), {**SAMPLE, 'name': 'HUMANA'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('name', response.data['errors'])

    def test_rejects_name_that_is_another_carriers_alias(self):
        make_carrier()
        response = self.client.post(self.create_url(), {**SAMPLE, 'name': 'humana inc', 'aliases': []}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('name', response.data['errors'])

    def test_rejects_alias_that_is_another_carriers_name(self):
        make_carrier()
        response = self.client.post(self.create_url(), {**SAMPLE, 'name': 'Other', 'aliases': ['humana']}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('aliases', response.data['errors'])

    def test_deleted_carriers_name_can_be_reused(self):
        make_carrier().delete()
        response = self.client.post(self.create_url(), SAMPLE, format='json')
        self.assertEqual(response.status_code, 201, response.data)


class CarrierListTests(CarrierAPITestCase):
    def test_lists_carriers_by_name(self):
        make_carrier(name='UHC', aliases=[])
        make_carrier()
        response = self.client.get(self.list_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual([c['name'] for c in response.data['data']], ['Humana', 'UHC'])
        self.assertEqual(response.data['meta']['total_items'], 2)

    def test_search_matches_alias(self):
        make_carrier(name='UHC', aliases=['United'])
        make_carrier()
        response = self.client.get(self.list_url(), {'search': 'united'})
        self.assertEqual([c['name'] for c in response.data['data']], ['UHC'])

    def test_filters_by_state_and_is_active(self):
        make_carrier(name='UHC', aliases=[], available_states=['CA'], status='inactive')
        make_carrier()
        response = self.client.get(self.list_url(), {'state': 'tx'})
        self.assertEqual([c['name'] for c in response.data['data']], ['Humana'])
        response = self.client.get(self.list_url(), {'is_active': 'false'})
        self.assertEqual([c['name'] for c in response.data['data']], ['UHC'])

    def test_hides_deleted_carriers(self):
        make_carrier().delete()
        response = self.client.get(self.list_url())
        self.assertEqual(response.data['data'], [])


class CarrierDetailTests(CarrierAPITestCase):
    def test_get(self):
        carrier = make_carrier()
        response = self.client.get(self.detail_url(carrier))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['available_states'], ['FL', 'LA', 'TX'])

    def test_patch_updates_states_and_records_note(self):
        carrier = make_carrier()
        response = self.client.patch(
            self.detail_url(carrier), {'licenses': [{'state': 'TX'}], 'status': 'inactive'}, format='json'
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['available_states'], ['TX'])
        self.assertFalse(response.data['data']['is_active'])
        note = carrier.notes.get()
        self.assertEqual(note.kind, 'edited')
        self.assertEqual(
            note.changes,
            [
                {'field': 'available_states', 'from': 'FL, LA, TX', 'to': 'TX'},
                {
                    'field': 'license_statuses',
                    'from': 'FL active, LA active, TX active',
                    'to': 'TX active',
                },
                {'field': 'status', 'from': 'active', 'to': 'inactive'},
            ],
        )

    def test_patch_saves_state_row_details(self):
        carrier = make_carrier(available_states=['TX'])
        row = {
            'state': 'TX',
            'license_number': ' 12345 ',
            'status': 'pending',
            'start_date': '2026-01-01',
            'end_date': '2028-01-01',
            'life': True,
            'health': True,
        }
        response = self.client.patch(self.detail_url(carrier), {'licenses': [row]}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        [saved] = response.data['data']['licenses']
        self.assertEqual(saved['license_number'], '12345')
        self.assertEqual(saved['status'], 'pending')
        self.assertEqual((saved['start_date'], saved['end_date']), ('2026-01-01', '2028-01-01'))
        self.assertTrue(saved['life'] and saved['health'])
        # The same row was kept, not replaced.
        self.assertEqual(CarrierStateLicense.all_objects.filter(carrier=carrier).count(), 1)
        self.assertEqual(
            [change['field'] for change in carrier.notes.get().changes],
            ['license_numbers', 'license_statuses', 'license_lines', 'license_dates'],
        )

    def test_removed_state_row_is_soft_deleted(self):
        carrier = make_carrier()
        response = self.client.patch(self.detail_url(carrier), {'licenses': [{'state': 'FL'}]}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([row['state'] for row in response.data['data']['licenses']], ['FL'])
        self.assertEqual(CarrierStateLicense.all_objects.deleted().filter(carrier=carrier).count(), 2)

    def test_rejects_expiration_before_start(self):
        carrier = make_carrier()
        row = {'state': 'TX', 'start_date': '2026-05-01', 'end_date': '2026-01-01'}
        response = self.client.patch(self.detail_url(carrier), {'licenses': [row]}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_patch_with_no_change_writes_no_note(self):
        carrier = make_carrier()
        response = self.client.patch(self.detail_url(carrier), {'name': 'Humana'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(carrier.notes.exists())

    def test_status_other_than_active_is_not_in_force(self):
        carrier = make_carrier()
        response = self.client.patch(self.detail_url(carrier), {'status': 'pending'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['status'], 'pending')
        self.assertFalse(response.data['data']['is_active'])
        self.assertEqual(
            carrier.notes.get().changes,
            [{'field': 'status', 'from': 'active', 'to': 'pending'}],
        )
        # ?is_active= still means "in force": a pending carrier is left out.
        response = self.client.get(self.list_url(), {'is_active': 'true'})
        self.assertEqual(response.data['data'], [])
        response = self.client.patch(self.detail_url(carrier), {'status': 'active'}, format='json')
        self.assertTrue(response.data['data']['is_active'])

    def test_rejects_unknown_status(self):
        carrier = make_carrier()
        response = self.client.patch(self.detail_url(carrier), {'status': 'paused'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('status', response.data['errors'])

    def test_patch_sets_and_clears_link(self):
        carrier = make_carrier()
        response = self.client.patch(self.detail_url(carrier), {'link': 'https://www.humana.com'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['link'], 'https://www.humana.com')
        self.assertEqual(
            carrier.notes.get().changes,
            [{'field': 'link', 'from': '', 'to': 'https://www.humana.com'}],
        )
        response = self.client.patch(self.detail_url(carrier), {'link': ''}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['link'], '')

    def test_patch_rejects_bad_link(self):
        carrier = make_carrier()
        response = self.client.patch(self.detail_url(carrier), {'link': 'not a url'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('link', response.data['errors'])

    def test_patch_keeps_own_name(self):
        carrier = make_carrier()
        response = self.client.patch(self.detail_url(carrier), {'name': 'HUMANA'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['name'], 'HUMANA')

    def test_patch_rejects_another_carriers_name(self):
        make_carrier(name='UHC', aliases=[])
        carrier = make_carrier()
        response = self.client.patch(self.detail_url(carrier), {'name': 'uhc'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('name', response.data['errors'])

    def test_patch_rejects_empty_lines(self):
        carrier = make_carrier()
        response = self.client.patch(self.detail_url(carrier), {'lines_of_business': []}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('lines_of_business', response.data['errors'])

    def test_delete_is_soft(self):
        carrier = make_carrier()
        response = self.client.delete(self.detail_url(carrier))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Carrier.objects.filter(pk=carrier.pk).exists())
        self.assertTrue(Carrier.all_objects.filter(pk=carrier.pk).exists())
        self.assertEqual(self.client.get(self.detail_url(carrier)).status_code, 404)

    def test_notes_newest_first(self):
        carrier = make_carrier()
        self.client.patch(self.detail_url(carrier), {'aliases': ['H']}, format='json')
        self.client.patch(self.detail_url(carrier), {'aliases': ['H', 'Hum']}, format='json')
        response = self.client.get(self.notes_url(carrier))
        self.assertEqual(response.status_code, 200)
        notes = response.data['data']
        self.assertEqual(len(notes), 2)
        self.assertEqual(notes[0]['changes'], [{'field': 'aliases', 'from': 'H', 'to': 'H, Hum'}])
        self.assertEqual(notes[0]['created_by'], 'Admin')


class CarrierPermissionTests(CarrierAPITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(email='staff@example.com', password='Sup3r-secret!', full_name='Staff')
        self.client.force_authenticate(self.staff)

    def test_anonymous_gets_401(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.list_url()).status_code, 401)

    def test_no_role_gets_403(self):
        self.assertEqual(self.client.get(self.list_url()).status_code, 403)

    def test_view_only_role_can_list_but_not_create(self):
        self.staff.roles.set([make_role(can_view=True)])
        self.assertEqual(self.client.get(self.list_url()).status_code, 200)
        self.assertEqual(self.client.post(self.create_url(), SAMPLE, format='json').status_code, 403)

    def test_create_role_can_create(self):
        self.staff.roles.set([make_role(can_view=True, can_create=True)])
        self.assertEqual(self.client.post(self.create_url(), SAMPLE, format='json').status_code, 201)


class DropGeneralMigrationTests(CarrierAPITestCase):
    def test_strips_general_and_keeps_carriers_left_with_no_lines(self):
        from importlib import import_module

        from django.apps import apps

        migration = import_module('apps.carriers.migrations.0004_drop_general_line')
        mixed = make_carrier(name='Mixed', aliases=[], lines_of_business=['General', 'MAPD'])
        only = make_carrier(name='Only', aliases=[], lines_of_business=['General'])
        migration.strip_general(apps, None)
        mixed.refresh_from_db()
        only.refresh_from_db()
        self.assertEqual(mixed.lines_of_business, ['MAPD'])
        self.assertEqual(only.lines_of_business, [])


class RenameSuppAncillaryMigrationTests(CarrierAPITestCase):
    def test_renames_supp_ancillary_to_ancillary(self):
        from importlib import import_module

        from django.apps import apps

        migration = import_module('apps.carriers.migrations.0005_rename_supp_ancillary')
        carrier = make_carrier(name='Both', aliases=[], lines_of_business=['Supp/Ancillary', 'MAPD'])
        migration.rename_forward(apps, None)
        carrier.refresh_from_db()
        self.assertEqual(carrier.lines_of_business, ['Ancillary', 'MAPD'])
