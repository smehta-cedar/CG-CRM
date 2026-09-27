from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.base.api.pagination import paginate
from apps.base.api.permissions import module_permission
from apps.base.api.response import APIResponse
from apps.contracts.models import AgencyCarrierContract, AgencyCarrierContractNote
from apps.contracts.utils import (
    agency_contract_queryset,
    agency_snapshot,
    diff_agency_snapshots,
    get_agency_contract_or_404,
    record_agency_note,
    save_agency_contract,
)
from apps.contracts.validators import (
    ensure_carrier_free,
    ensure_login_pair,
    resolve_agency,
    resolve_carrier,
    resolve_policies,
)

from . import swagger
from .serializers import (
    AgencyContractCreateSerializer,
    AgencyContractListQuerySerializer,
    AgencyContractNoteSerializer,
    AgencyContractSerializer,
    AgencyContractUpdateSerializer,
)

CAN_MANAGE_AGENCY_CONTRACTS = module_permission('agency_contracts')


def _clean_password(password):
    """Spaces alone count as blank; anything else is kept as typed."""
    return password if password.strip() else ''


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
    policies = resolve_policies(data.get('policies', []), carrier)
    username = data.get('username', '').strip()
    password = _clean_password(data.get('password', ''))
    ensure_login_pair(username, password)

    with transaction.atomic():
        contract = AgencyCarrierContract.objects.create(
            agency=agency,
            carrier=carrier,
            contract_number=data.get('contract_number', ''),
            username=username,
            password=password,
            is_active=data.get('is_active', True),
            created_by=request.user,
            updated_by=request.user,
        )
        contract.policies.set(policies)
        contract = get_agency_contract_or_404(contract.pk)
        # The note lists every filled field, as the contract now reads.
        record_agency_note(
            contract,
            request.user,
            AgencyCarrierContractNote.KIND_ADDED,
            diff_agency_snapshots({}, agency_snapshot(contract)),
        )

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

        # Policies are re-checked whenever they or the carrier change, so a
        # contract never covers another carrier's policy.
        policies = None
        if 'policies' in fields:
            policies = resolve_policies(fields.pop('policies'), carrier)
        elif carrier != contract.carrier:
            resolve_policies([policy.pk for policy in contract.policies.all()], carrier)

        if 'username' in fields:
            fields['username'] = fields['username'].strip()
        if 'password' in fields:
            fields['password'] = _clean_password(fields['password'])
        ensure_login_pair(fields.get('username', contract.username), fields.get('password', contract.password))

        before = agency_snapshot(contract)
        with transaction.atomic():
            save_agency_contract(contract, request.user, policies=policies, **fields)
            # Read the policies again for the note and the response.
            contract = get_agency_contract_or_404(pk)
            record_agency_note(
                contract,
                request.user,
                AgencyCarrierContractNote.KIND_EDITED,
                diff_agency_snapshots(before, agency_snapshot(contract)),
            )
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
