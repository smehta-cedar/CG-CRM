from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Role, RolePermission, User
from apps.agency.models import State
from apps.carriers.models import Carrier

from .models import CarrierPolicy, CarrierPolicyNote, PolicyType


def make_carrier(name='Humana', codes=('FL', 'TX', 'LA')):
    carrier = Carrier.objects.create(name=name, lines_of_business=['MAPD'])
    carrier.available_states.set(State.objects.filter(code__in=codes))
    return carrier


def make_policy_type(name='Medicare Advantage', **overrides):
    return PolicyType.objects.create(name=name, **overrides)


def make_policy(carrier, policy_type, name='Gold Plus HMO', codes=('FL', 'TX'), **overrides):
    policy = CarrierPolicy.objects.create(carrier=carrier, policy_type=policy_type, name=name, **overrides)
    policy.available_states.set(State.objects.filter(code__in=codes))
    return policy


def make_role(module, **flags):
    role = Role.objects.create(name=f"{module}-{'-'.join(k for k, v in flags.items() if v) or 'none'}")
    RolePermission.objects.create(role=role, module=module, **flags)
    return role


class CarrierPolicyAPITestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='Sup3r-secret!', full_name='Admin')
        self.client.force_authenticate(self.admin)
        self.carrier = make_carrier()
        self.policy_type = make_policy_type()
        self.sample = {
            'carrier': str(self.carrier.pk),
            'policy_type': str(self.policy_type.pk),
            'name': 'Gold Plus HMO',
            'available_states': ['TX', 'FL'],
        }

    def list_url(self):
        return reverse('policies:apis:carrier_policies:list')

    def create_url(self):
        return reverse('policies:apis:carrier_policies:create')

    def detail_url(self, policy):
        return reverse('policies:apis:carrier_policies:detail', args=[policy.pk])

    def notes_url(self, policy):
        return reverse('policies:apis:carrier_policies:notes', args=[policy.pk])


class CarrierPolicyCreateTests(CarrierPolicyAPITestCase):
    def test_creates_policy_from_sample(self):
        response = self.client.post(self.create_url(), self.sample, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data['data']
        self.assertEqual(data['name'], 'Gold Plus HMO')
        self.assertEqual(data['carrier']['name'], 'Humana')
        self.assertEqual(data['policy_type']['name'], 'Medicare Advantage')
        # States come back in code order whatever order they were sent in.
        self.assertEqual(data['available_states'], ['FL', 'TX'])
        self.assertTrue(data['is_active'])
        policy = CarrierPolicy.objects.get(pk=data['id'])
        self.assertEqual(policy.created_by, self.admin)

    def test_records_an_added_note_in_field_order(self):
        response = self.client.post(self.create_url(), self.sample, format='json')
        note = CarrierPolicyNote.objects.get(policy_id=response.data['data']['id'])
        self.assertEqual(note.kind, 'added')
        self.assertEqual(note.created_by, self.admin)
        self.assertEqual(
            note.changes,
            [
                {'field': 'name', 'from': '', 'to': 'Gold Plus HMO'},
                {'field': 'policy_type', 'from': '', 'to': 'Medicare Advantage'},
                {'field': 'carrier', 'from': '', 'to': 'Humana'},
                {'field': 'available_states', 'from': '', 'to': 'FL, TX'},
                {'field': 'status', 'from': '', 'to': 'active'},
            ],
        )

    def test_states_default_to_none(self):
        response = self.client.post(self.create_url(), {**self.sample, 'available_states': []}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['data']['available_states'], [])
        # An empty list is not listed on the note.
        note = CarrierPolicyNote.objects.get(policy_id=response.data['data']['id'])
        self.assertNotIn('available_states', [change['field'] for change in note.changes])

    def test_carrier_policy_type_and_name_are_required(self):
        response = self.client.post(self.create_url(), {}, format='json')
        self.assertEqual(response.status_code, 400)
        for field in ('carrier', 'policy_type', 'name'):
            self.assertIn(field, response.data['errors'])

    def test_unknown_carrier_and_policy_type_are_400(self):
        unknown = '00000000-0000-0000-0000-000000000000'
        response = self.client.post(self.create_url(), {**self.sample, 'carrier': unknown}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('carrier', response.data['errors'])
        response = self.client.post(self.create_url(), {**self.sample, 'policy_type': unknown}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('policy_type', response.data['errors'])

    def test_rejects_state_outside_carrier_footprint_and_names_it(self):
        response = self.client.post(self.create_url(), {**self.sample, 'available_states': ['FL', 'AK']}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['available_states'], ['Humana is not available in AK.'])

    def test_rejects_unknown_state_code(self):
        response = self.client.post(self.create_url(), {**self.sample, 'available_states': ['ZZ']}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('available_states', response.data['errors'])

    def test_rejects_duplicate_name_on_same_carrier_case_insensitively(self):
        make_policy(self.carrier, self.policy_type)
        response = self.client.post(self.create_url(), {**self.sample, 'name': 'GOLD PLUS HMO'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['name'], ['This carrier already has a policy with this name.'])

    def test_another_carrier_may_use_the_same_name(self):
        other = make_carrier(name='Aetna', codes=('FL', 'TX'))
        make_policy(other, self.policy_type)
        response = self.client.post(self.create_url(), self.sample, format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def test_deleted_policy_name_can_be_reused(self):
        make_policy(self.carrier, self.policy_type).delete()
        response = self.client.post(self.create_url(), self.sample, format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def test_name_is_trimmed(self):
        response = self.client.post(self.create_url(), {**self.sample, 'name': '  Gold   Plus '}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['data']['name'], 'Gold Plus')


class CarrierPolicyListTests(CarrierPolicyAPITestCase):
    def test_lists_policies_by_name_with_filters(self):
        other_carrier = make_carrier(name='Aetna', codes=('FL',))
        other_type = make_policy_type(name='Dental')
        make_policy(self.carrier, self.policy_type, name='Silver PPO', codes=('TX',))
        make_policy(self.carrier, other_type, name='Bright Smile', codes=(), is_active=False)
        make_policy(other_carrier, self.policy_type, name='Aetna Gold', codes=('FL',))

        response = self.client.get(self.list_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual([p['name'] for p in response.data['data']], ['Aetna Gold', 'Bright Smile', 'Silver PPO'])
        self.assertEqual(response.data['meta']['total_items'], 3)

        response = self.client.get(self.list_url(), {'carrier': str(self.carrier.pk)})
        self.assertEqual([p['name'] for p in response.data['data']], ['Bright Smile', 'Silver PPO'])

        response = self.client.get(self.list_url(), {'policy_type': str(other_type.pk)})
        self.assertEqual([p['name'] for p in response.data['data']], ['Bright Smile'])

        response = self.client.get(self.list_url(), {'is_active': 'false'})
        self.assertEqual([p['name'] for p in response.data['data']], ['Bright Smile'])

        response = self.client.get(self.list_url(), {'search': 'gold'})
        self.assertEqual([p['name'] for p in response.data['data']], ['Aetna Gold'])

    def test_bad_carrier_filter_is_400(self):
        response = self.client.get(self.list_url(), {'carrier': 'not-a-uuid'})
        self.assertEqual(response.status_code, 400)

    def test_hides_deleted_policies(self):
        make_policy(self.carrier, self.policy_type).delete()
        response = self.client.get(self.list_url())
        self.assertEqual(response.data['data'], [])


class CarrierPolicyDetailTests(CarrierPolicyAPITestCase):
    def test_get(self):
        policy = make_policy(self.carrier, self.policy_type)
        response = self.client.get(self.detail_url(policy))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['name'], 'Gold Plus HMO')
        self.assertEqual(response.data['data']['carrier']['id'], str(self.carrier.pk))

    def test_patch_updates_fields_and_records_note(self):
        policy = make_policy(self.carrier, self.policy_type)
        dental = make_policy_type(name='Dental')
        response = self.client.patch(
            self.detail_url(policy),
            {'name': 'Gold Plus PPO', 'policy_type': str(dental.pk), 'available_states': ['LA'], 'is_active': False},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data['data']
        self.assertEqual(data['name'], 'Gold Plus PPO')
        self.assertEqual(data['policy_type']['name'], 'Dental')
        self.assertEqual(data['available_states'], ['LA'])
        self.assertFalse(data['is_active'])
        note = policy.notes.get()
        self.assertEqual(note.kind, 'edited')
        self.assertEqual(
            note.changes,
            [
                {'field': 'name', 'from': 'Gold Plus HMO', 'to': 'Gold Plus PPO'},
                {'field': 'policy_type', 'from': 'Medicare Advantage', 'to': 'Dental'},
                {'field': 'available_states', 'from': 'FL, TX', 'to': 'LA'},
                {'field': 'status', 'from': 'active', 'to': 'inactive'},
            ],
        )

    def test_patch_with_no_change_writes_no_note(self):
        policy = make_policy(self.carrier, self.policy_type)
        response = self.client.patch(
            self.detail_url(policy), {'name': 'Gold Plus HMO', 'available_states': ['TX', 'FL']}, format='json'
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(policy.notes.exists())

    def test_patch_rejects_state_outside_carrier_footprint(self):
        policy = make_policy(self.carrier, self.policy_type)
        response = self.client.patch(self.detail_url(policy), {'available_states': ['FL', 'CA']}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['available_states'], ['Humana is not available in CA.'])

    def test_patch_keeps_own_name_but_rejects_a_sibling_name(self):
        policy = make_policy(self.carrier, self.policy_type)
        make_policy(self.carrier, self.policy_type, name='Silver PPO', codes=())
        response = self.client.patch(self.detail_url(policy), {'name': 'GOLD PLUS HMO'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        response = self.client.patch(self.detail_url(policy), {'name': 'silver ppo'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('name', response.data['errors'])

    def test_patch_ignores_carrier(self):
        policy = make_policy(self.carrier, self.policy_type)
        other = make_carrier(name='Aetna', codes=('FL',))
        response = self.client.patch(self.detail_url(policy), {'carrier': str(other.pk)}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['carrier']['name'], 'Humana')

    def test_delete_is_soft(self):
        policy = make_policy(self.carrier, self.policy_type)
        response = self.client.delete(self.detail_url(policy))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CarrierPolicy.objects.filter(pk=policy.pk).exists())
        self.assertTrue(CarrierPolicy.all_objects.filter(pk=policy.pk).exists())
        self.assertEqual(self.client.get(self.detail_url(policy)).status_code, 404)

    def test_notes_newest_first(self):
        policy = make_policy(self.carrier, self.policy_type)
        self.client.patch(self.detail_url(policy), {'name': 'Gold'}, format='json')
        self.client.patch(self.detail_url(policy), {'name': 'Gold Plus'}, format='json')
        response = self.client.get(self.notes_url(policy))
        self.assertEqual(response.status_code, 200)
        notes = response.data['data']
        self.assertEqual(len(notes), 2)
        self.assertEqual(notes[0]['changes'], [{'field': 'name', 'from': 'Gold', 'to': 'Gold Plus'}])
        self.assertEqual(notes[0]['created_by'], 'Admin')


class CarrierPolicyPermissionTests(CarrierPolicyAPITestCase):
    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_user(email='staff@example.com', password='Sup3r-secret!', full_name='Staff')
        self.client.force_authenticate(self.staff)

    def test_anonymous_gets_401(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.list_url()).status_code, 401)

    def test_no_role_gets_403(self):
        self.assertEqual(self.client.get(self.list_url()).status_code, 403)

    def test_carriers_view_only_role_can_list_but_not_create(self):
        self.staff.roles.set([make_role('carriers', can_view=True)])
        self.assertEqual(self.client.get(self.list_url()).status_code, 200)
        self.assertEqual(self.client.post(self.create_url(), self.sample, format='json').status_code, 403)

    def test_carriers_create_role_can_create(self):
        self.staff.roles.set([make_role('carriers', can_view=True, can_create=True)])
        self.assertEqual(self.client.post(self.create_url(), self.sample, format='json').status_code, 201)

    def test_policy_types_role_alone_is_not_enough(self):
        self.staff.roles.set([make_role('policy_types', can_view=True, can_create=True)])
        self.assertEqual(self.client.get(self.list_url()).status_code, 403)
