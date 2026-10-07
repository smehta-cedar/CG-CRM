from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.base.api.pagination import paginate
from apps.base.api.permissions import module_permission
from apps.base.api.response import APIResponse
from apps.policies.models import CarrierPolicy, CarrierPolicyNote
from apps.policies.utils import (
    POLICY_NOTE_FIELDS,
    diff_snapshots,
    filter_policies,
    get_policy_or_404,
    normalize_name,
    policy_queryset,
    policy_snapshot,
    record_policy_note,
    save_policy,
    search_policies,
)
from apps.policies.validators import (
    ensure_policy_name_free,
    resolve_carrier,
    resolve_policy_states,
    resolve_policy_type,
)

from . import swagger
from .serializers import (
    CarrierPolicyCreateSerializer,
    CarrierPolicyListQuerySerializer,
    CarrierPolicyNoteSerializer,
    CarrierPolicySerializer,
    CarrierPolicyUpdateSerializer,
)

# A policy lives on its carrier, so the carriers permission covers it.
CAN_MANAGE_CARRIER_POLICIES = module_permission('carriers')


@swagger.carrier_policy_list
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_CARRIER_POLICIES])
def carrier_policy_list(request):
    # Check the ?search=, ?carrier=, ?policy_type= and ?is_active= values; bad ones give a 400.
    query = CarrierPolicyListQuerySerializer(data=request.query_params.dict())
    query.is_valid(raise_exception=True)
    filters = query.validated_data

    policies = policy_queryset()

    search = filters.get('search')
    if search:
        policies = search_policies(policies, search)

    policies = filter_policies(
        policies,
        carrier=filters.get('carrier'),
        policy_type=filters.get('policy_type'),
        is_active=filters.get('is_active'),
    )

    # Cut the requested page (?page=, ?page_size=); meta holds the page numbers and totals.
    page, meta = paginate(request, policies.order_by('name'))
    serializer = CarrierPolicySerializer(page, many=True)
    return APIResponse(serializer.data, 'Carrier policies fetched successfully.', meta=meta)


@swagger.carrier_policy_create
@api_view(['POST'])
@permission_classes([IsAuthenticated, CAN_MANAGE_CARRIER_POLICIES])
def carrier_policy_create(request):
    serializer = CarrierPolicyCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    carrier = resolve_carrier(data['carrier'])
    policy_type = resolve_policy_type(data.get('policy_type'))
    name = normalize_name(data['name'])
    ensure_policy_name_free(carrier, name)
    states = resolve_policy_states(data.get('available_states', []), carrier)

    with transaction.atomic():
        policy = CarrierPolicy.objects.create(
            carrier=carrier,
            policy_type=policy_type,
            name=name,
            is_active=data.get('is_active', True),
            created_by=request.user,
            updated_by=request.user,
        )
        policy.available_states.set(states)
        # The note lists every filled field, as the policy now reads.
        record_policy_note(
            policy,
            request.user,
            CarrierPolicyNote.KIND_ADDED,
            diff_snapshots({}, policy_snapshot(policy), POLICY_NOTE_FIELDS),
        )

    return APIResponse(
        CarrierPolicySerializer(policy).data,
        'Carrier policy created successfully.',
        status=status.HTTP_201_CREATED,
    )


@swagger.carrier_policy_detail
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, CAN_MANAGE_CARRIER_POLICIES])
def carrier_policy_detail(request, pk):
    policy = get_policy_or_404(pk)

    if request.method == 'GET':
        return APIResponse(CarrierPolicySerializer(policy).data, 'Carrier policy fetched successfully.')

    if request.method == 'PATCH':
        # partial=True: only the fields that were sent get updated.
        serializer = CarrierPolicyUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields = dict(serializer.validated_data)

        if 'policy_type' in fields:
            fields['policy_type'] = resolve_policy_type(fields['policy_type'])

        # The name only has to be free when it is actually changing.
        if 'name' in fields:
            fields['name'] = name = normalize_name(fields['name'])
            if name.lower() != policy.name.lower():
                ensure_policy_name_free(policy.carrier, name, exclude=policy)

        states = None
        if 'available_states' in fields:
            states = resolve_policy_states(fields.pop('available_states'), policy.carrier)

        before = policy_snapshot(policy)
        with transaction.atomic():
            save_policy(policy, request.user, states=states, **fields)
            policy = get_policy_or_404(pk)  # fresh states for the note and the response
            record_policy_note(
                policy,
                request.user,
                CarrierPolicyNote.KIND_EDITED,
                diff_snapshots(before, policy_snapshot(policy), POLICY_NOTE_FIELDS),
            )
        return APIResponse(CarrierPolicySerializer(policy).data, 'Carrier policy updated successfully.')

    # DELETE: soft delete; the name becomes free for the carrier to reuse.
    policy.delete(user=request.user)
    return APIResponse(None, 'Carrier policy deleted successfully.')


@swagger.carrier_policy_notes
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_CARRIER_POLICIES])
def carrier_policy_notes(request, pk):
    policy = get_policy_or_404(pk)
    # Newest first (the model's ordering). Not paginated: a policy has a handful.
    notes = policy.notes.select_related('created_by')
    return APIResponse(CarrierPolicyNoteSerializer(notes, many=True).data, 'Carrier policy notes fetched successfully.')
