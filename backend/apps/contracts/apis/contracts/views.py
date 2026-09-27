from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.base.api.pagination import paginate
from apps.base.api.permissions import module_permission
from apps.base.api.response import APIResponse
from apps.contracts.models import CarrierContract, CarrierContractNote
from apps.contracts.utils import (
    diff_snapshots,
    filter_contracts,
    get_contract_or_404,
    record_note,
    save_contract,
    search_contracts,
    snapshot,
)
from apps.contracts.validators import (
    ensure_carrier_accessible,
    ensure_pair_free,
    ensure_within_ceiling,
    ensure_writing_number_free,
    resolve_states,
)

from . import swagger
from .serializers import (
    ContractCreateSerializer,
    ContractListQuerySerializer,
    ContractNoteSerializer,
    ContractSerializer,
    ContractUpdateSerializer,
)

CAN_MANAGE_CONTRACTS = module_permission('contracts')


@swagger.contract_list
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_CONTRACTS])
def contract_list(request):
    # Check the ?search=, ?agent_id=, ?carrier_id= and ?state= values; bad ones give a 400.
    query = ContractListQuerySerializer(data=request.query_params.dict())
    query.is_valid(raise_exception=True)
    filters = query.validated_data

    contracts = CarrierContract.objects.select_related('agent', 'carrier').prefetch_related('appointed_states')

    search = filters.get('search')
    if search:
        contracts = search_contracts(contracts, search)

    contracts = filter_contracts(
        contracts,
        agent_id=filters.get('agent_id'),
        carrier_id=filters.get('carrier_id'),
        state=filters.get('state'),
    ).distinct()

    # Cut the requested page (?page=, ?page_size=); meta holds the page numbers and totals.
    page, meta = paginate(request, contracts.order_by('agent__name', 'carrier__name'))
    serializer = ContractSerializer(page, many=True)
    return APIResponse(serializer.data, 'Contracts fetched successfully.', meta=meta)


@swagger.contract_create
@api_view(['POST'])
@permission_classes([IsAuthenticated, CAN_MANAGE_CONTRACTS])
def contract_create(request):
    serializer = ContractCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    agent, carrier = data['agent'], data['carrier']
    writing_number = data.get('writing_number', '').strip()
    ensure_carrier_accessible(carrier)
    ensure_pair_free(agent, carrier)
    ensure_writing_number_free(writing_number, carrier)
    states = resolve_states(data.get('appointed_states', []))
    ensure_within_ceiling(states, agent, carrier)

    with transaction.atomic():
        contract = CarrierContract.objects.create(
            agent=agent,
            carrier=carrier,
            writing_number=writing_number,
            created_by=request.user,
            updated_by=request.user,
        )
        contract.appointed_states.set(states)
        # The note lists every filled field, as the contract now reads.
        record_note(contract, request.user, CarrierContractNote.KIND_ADDED, diff_snapshots({}, snapshot(contract)))

    return APIResponse(ContractSerializer(contract).data, 'Contract created successfully.', status=status.HTTP_201_CREATED)


@swagger.contract_detail
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, CAN_MANAGE_CONTRACTS])
def contract_detail(request, pk):
    contract = get_contract_or_404(pk)

    if request.method == 'GET':
        return APIResponse(ContractSerializer(contract).data, 'Contract fetched successfully.')

    if request.method == 'PATCH':
        # partial=True: only the fields that were sent get updated.
        serializer = ContractUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields = dict(serializer.validated_data)

        agent = fields.get('agent', contract.agent)
        carrier = fields.get('carrier', contract.carrier)
        # Moving to another carrier needs that carrier open to agents; keeping it doesn't.
        if carrier != contract.carrier:
            ensure_carrier_accessible(carrier)
        # The pair only has to be free when it is actually changing.
        if agent != contract.agent or carrier != contract.carrier:
            ensure_pair_free(agent, carrier, exclude=contract)

        writing_number = fields.get('writing_number', contract.writing_number).strip()
        if 'writing_number' in fields:
            fields['writing_number'] = writing_number
        if writing_number.lower() != contract.writing_number.lower() or carrier != contract.carrier:
            ensure_writing_number_free(writing_number, carrier, exclude=contract)

        # The ceiling is re-checked whenever the pair or the states change.
        states = None
        if 'appointed_states' in fields:
            states = resolve_states(fields.pop('appointed_states'))
        if states is not None or agent != contract.agent or carrier != contract.carrier:
            ensure_within_ceiling(states if states is not None else list(contract.appointed_states.all()), agent, carrier)

        before = snapshot(contract)
        with transaction.atomic():
            save_contract(contract, request.user, states=states, **fields)
            # Read the states again for the note and the response.
            contract = get_contract_or_404(pk)
            record_note(contract, request.user, CarrierContractNote.KIND_EDITED, diff_snapshots(before, snapshot(contract)))
        return APIResponse(ContractSerializer(contract).data, 'Contract updated successfully.')

    # DELETE: soft delete; the agent + carrier pair becomes free again.
    contract.delete(user=request.user)
    return APIResponse(None, 'Contract deleted successfully.')


@swagger.contract_notes
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_CONTRACTS])
def contract_notes(request, pk):
    contract = get_contract_or_404(pk)
    # Newest first (the model's ordering). Not paginated: a contract has a handful.
    notes = contract.notes.select_related('created_by')
    return APIResponse(ContractNoteSerializer(notes, many=True).data, 'Contract notes fetched successfully.')


@swagger.contract_notes_all
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_CONTRACTS])
def contract_notes_all(request):
    """Every live contract's notes, newest first, for the Contracts page's expandable rows."""
    notes = CarrierContractNote.objects.filter(contract__deleted_at__isnull=True).select_related('created_by')
    page, meta = paginate(request, notes)
    return APIResponse(ContractNoteSerializer(page, many=True).data, 'Contract notes fetched successfully.', meta=meta)
