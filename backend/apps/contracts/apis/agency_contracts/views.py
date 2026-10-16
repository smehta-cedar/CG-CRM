from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.base.api.pagination import paginate
from apps.base.api.permissions import module_permission
from apps.base.api.response import APIResponse
from apps.contracts.models import (
    AgencyCarrierContract,
    AgencyCarrierContractNote,
    CarrierContract,
    CarrierContractNote,
)
from apps.contracts.utils import (
    agency_contract_queryset,
    agency_snapshot,
    diff_agency_snapshots,
    diff_snapshots,
    get_agency_contract_or_404,
    record_agency_note,
    record_note,
    save_agency_contract,
    snapshot,
)
from apps.contracts.validators import (
    ensure_can_appoint,
    ensure_carrier_free,
    ensure_number_when_active,
    resolve_agency,
    resolve_agents,
    resolve_carrier,
    resolve_policy_types,
)
from apps.passwords.utils import add_pending_password
from apps.policies.utils import add_contract_certifications

from . import swagger
from .serializers import (
    AgencyContractCreateSerializer,
    AgencyContractListQuerySerializer,
    AgencyContractNoteSerializer,
    AgencyContractSerializer,
    AgencyContractUpdateSerializer,
)

CAN_MANAGE_AGENCY_CONTRACTS = module_permission('agencies')


def appoint_agents(agents, carrier, actor):
    """Appoint each of `agents` with `carrier`, as the Contracts page's add
    would: a pending appointment with no writing number or states, its
    "added" note, this year's certifications and a pending password. Agents
    already appointed there are skipped."""
    taken = set(CarrierContract.objects.filter(carrier=carrier, agent__in=agents).values_list('agent_id', flat=True))
    for agent in agents:
        if agent.pk in taken:
            continue
        contract = CarrierContract.objects.create(
            agent=agent,
            carrier=carrier,
            status='pending',
            created_by=actor,
            updated_by=actor,
        )
        record_note(contract, actor, CarrierContractNote.KIND_ADDED, diff_snapshots({}, snapshot(contract)))
        add_contract_certifications(agent, carrier, actor)
        add_pending_password(carrier, actor, agent=agent)


@swagger.agency_contract_list
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_AGENCY_CONTRACTS])
def agency_contract_list(request):
    # Check the ?agency= and ?carrier= values; bad ones give a 400.
    query = AgencyContractListQuerySerializer(data=request.query_params.dict())
    query.is_valid(raise_exception=True)
    filters = query.validated_data

    contracts = agency_contract_queryset()
    if filters.get('agency') is not None:
        contracts = contracts.filter(agency_id=filters['agency'])
    if filters.get('carrier') is not None:
        contracts = contracts.filter(carrier_id=filters['carrier'])

    # Cut the requested page (?page=, ?page_size=); meta holds the page numbers and totals.
    page, meta = paginate(request, contracts.order_by('carrier__name'))
    serializer = AgencyContractSerializer(page, many=True)
    return APIResponse(serializer.data, 'Agency contracts fetched successfully.', meta=meta)


@swagger.agency_contract_create
@api_view(['POST'])
@permission_classes([IsAuthenticated, CAN_MANAGE_AGENCY_CONTRACTS])
def agency_contract_create(request):
    serializer = AgencyContractCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    agency = resolve_agency(data['agency'])
    carrier = resolve_carrier(data['carrier'])
    ensure_carrier_free(carrier)
    policy_types = resolve_policy_types(data.get('policy_types', []))
    contract_number = data.get('contract_number', '')
    contract_status = data.get('status', 'active')
    ensure_number_when_active(contract_number, contract_status)
    agents = resolve_agents(data.get('agents', []))
    if agents:
        ensure_can_appoint(request.user, carrier, contract_number, contract_status)

    with transaction.atomic():
        contract = AgencyCarrierContract.objects.create(
            agency=agency,
            carrier=carrier,
            contract_number=contract_number,
            status=contract_status,
            created_by=request.user,
            updated_by=request.user,
        )
        contract.policy_types.set(policy_types)
        contract = get_agency_contract_or_404(contract.pk)
        # The note lists every filled field, as the contract now reads.
        record_agency_note(
            contract,
            request.user,
            AgencyCarrierContractNote.KIND_ADDED,
            diff_agency_snapshots({}, agency_snapshot(contract)),
        )
        # The agency gets a pending password at the carrier to fill in once the login is issued.
        add_pending_password(carrier, request.user, agency=agency)
        appoint_agents(agents, carrier, request.user)

    return APIResponse(
        AgencyContractSerializer(contract).data,
        'Agency contract created successfully.',
        status=status.HTTP_201_CREATED,
    )


@swagger.agency_contract_detail
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, CAN_MANAGE_AGENCY_CONTRACTS])
def agency_contract_detail(request, pk):
    contract = get_agency_contract_or_404(pk)

    if request.method == 'GET':
        return APIResponse(AgencyContractSerializer(contract).data, 'Agency contract fetched successfully.')

    if request.method == 'PATCH':
        # partial=True: only the fields that were sent get updated.
        serializer = AgencyContractUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields = dict(serializer.validated_data)

        if 'agency' in fields:
            fields['agency'] = resolve_agency(fields['agency'])
        if 'carrier' in fields:
            fields['carrier'] = resolve_carrier(fields['carrier'])
        carrier = fields.get('carrier', contract.carrier)
        # The carrier only has to be free when it is actually changing.
        if carrier != contract.carrier:
            ensure_carrier_free(carrier, exclude=contract)

        policy_types = None
        if 'policy_types' in fields:
            policy_types = resolve_policy_types(fields.pop('policy_types'))

        contract_number = fields.get('contract_number', contract.contract_number)
        contract_status = fields.get('status', contract.status)
        # Only checked when the number or status is sent, so an older active
        # contract with no number can still have its policy types edited.
        if 'contract_number' in fields or 'status' in fields:
            ensure_number_when_active(contract_number, contract_status)
        agents = resolve_agents(fields.pop('agents', []))
        if agents:
            ensure_can_appoint(request.user, carrier, contract_number, contract_status)

        # Only a carrier new to the contract gets a pending password, so one that
        # was deleted on purpose isn't brought back by an unrelated edit.
        new_carrier = carrier != contract.carrier
        before = agency_snapshot(contract)
        with transaction.atomic():
            save_agency_contract(contract, request.user, policy_types=policy_types, **fields)
            # Read the policy types again for the note and the response.
            contract = get_agency_contract_or_404(pk)
            record_agency_note(
                contract,
                request.user,
                AgencyCarrierContractNote.KIND_EDITED,
                diff_agency_snapshots(before, agency_snapshot(contract)),
            )
            if new_carrier:
                add_pending_password(contract.carrier, request.user, agency=contract.agency)
            appoint_agents(agents, contract.carrier, request.user)
        return APIResponse(AgencyContractSerializer(contract).data, 'Agency contract updated successfully.')

    # DELETE: soft delete; the carrier can be contracted again.
    contract.delete(user=request.user)
    return APIResponse(None, 'Agency contract deleted successfully.')


@swagger.agency_contract_notes
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_AGENCY_CONTRACTS])
def agency_contract_notes(request, pk):
    contract = get_agency_contract_or_404(pk)
    # Newest first (the model's ordering). Not paginated: a contract has a handful.
    notes = contract.notes.select_related('created_by')
    return APIResponse(AgencyContractNoteSerializer(notes, many=True).data, 'Agency contract notes fetched successfully.')
