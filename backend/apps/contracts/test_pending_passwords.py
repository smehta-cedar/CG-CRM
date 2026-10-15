from io import StringIO

from django.core.management import call_command

from apps.agency.models import State
from apps.contracts.models import AgencyCarrierContract
from apps.passwords.models import Password

from .test_agency_contracts import AgencyContractAPITestCase
from .tests import ContractAPITestCase


class AgentPendingPasswordTests(ContractAPITestCase):
    """Adding a carrier to an agent gives them a pending password there."""

    def test_new_contract_adds_a_pending_password(self):
        response = self.client.post(self.create_url(), self.sample, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        password = Password.objects.get(agent=self.agent, carrier=self.carrier)
        self.assertEqual((password.status, password.username, password.portal_password), ('pending', '', ''))
        self.assertEqual(password.created_by, self.admin)
        self.assertEqual(password.notes.get().kind, 'added')

    def test_existing_password_is_kept(self):
        Password.objects.create(agent=self.agent, carrier=self.carrier, username='malva', portal_password='p')
        self.client.post(self.create_url(), self.sample, format='json')
        self.assertEqual(Password.objects.get(agent=self.agent, carrier=self.carrier).status, 'active')

    def test_moving_to_another_carrier_adds_one_there(self):
        contract = self.make_contract(states=['TX'])
        # UHC has no states in setUp; the move needs TX within its footprint.
        self.other_carrier.available_states.set(State.objects.filter(code='TX'))
        response = self.client.patch(self.detail_url(contract), {'carrier_id': str(self.other_carrier.pk)}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(Password.objects.filter(agent=self.agent, carrier=self.other_carrier, status='pending').exists())

    def test_unrelated_edit_does_not_bring_a_deleted_password_back(self):
        contract = self.make_contract(states=['TX'])
        response = self.client.patch(self.detail_url(contract), {'status': 'pending'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(Password.objects.filter(agent=self.agent, carrier=self.carrier).exists())


class AgencyPendingPasswordTests(AgencyContractAPITestCase):
    """Adding a carrier to the agency gives the agency a pending password there."""

    def test_new_agency_contract_adds_a_pending_password(self):
        response = self.client.post(self.create_url(), self.sample, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        password = Password.objects.get(agency=self.agency, carrier=self.carrier)
        self.assertEqual(password.status, 'pending')
        self.assertIsNone(password.agent)

    def test_unnumbered_contract_still_gets_one(self):
        response = self.client.post(
            self.create_url(), {**self.sample, 'contract_number': '', 'status': 'pending'}, format='json'
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(Password.objects.filter(agency=self.agency, carrier=self.carrier).exists())

    def test_moving_to_another_carrier_adds_one_there(self):
        contract = self.make_contract()
        response = self.client.patch(self.detail_url(contract), {'carrier': str(self.other_carrier.pk)}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(Password.objects.filter(agency=self.agency, carrier=self.other_carrier).exists())


class BackfillCommandTests(ContractAPITestCase):
    def test_adds_missing_pending_passwords_once(self):
        # setUp gave the agency contracts at both carriers; give the agent one too.
        self.make_contract(states=['TX'])
        call_command('add_pending_passwords', stdout=StringIO())
        self.assertTrue(Password.objects.filter(agent=self.agent, carrier=self.carrier, status='pending').exists())
        self.assertEqual(Password.objects.filter(agency=self.agency).count(), AgencyCarrierContract.objects.count())
        before = Password.objects.count()
        call_command('add_pending_passwords', stdout=StringIO())
        self.assertEqual(Password.objects.count(), before)
