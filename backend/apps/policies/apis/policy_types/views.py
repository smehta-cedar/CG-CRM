from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.base.api.pagination import paginate
from apps.base.api.permissions import module_permission
from apps.base.api.response import APIResponse
from apps.policies.models import PolicyType, PolicyTypeNote
from apps.policies.utils import (
    NOTE_FIELDS,
    diff_snapshots,
    filter_policy_types,
    get_policy_type_or_404,
    normalize_name,
    policy_type_queryset,
    record_note,
    save_policy_type,
    search_policy_types,
    snapshot,
)
from apps.policies.validators import ensure_name_free

from . import swagger
from .serializers import (
    PolicyTypeCreateSerializer,
    PolicyTypeListQuerySerializer,
    PolicyTypeNoteSerializer,
    PolicyTypeSerializer,
    PolicyTypeUpdateSerializer,
)

CAN_MANAGE_POLICY_TYPES = module_permission('policy_types')


@swagger.policy_type_list
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_POLICY_TYPES])
def policy_type_list(request):
    # Check the ?search= and ?is_active= values; bad ones give a 400.
    query = PolicyTypeListQuerySerializer(data=request.query_params.dict())
    query.is_valid(raise_exception=True)
    filters = query.validated_data

    policy_types = policy_type_queryset()

    search = filters.get('search')
    if search:
        policy_types = search_policy_types(policy_types, search)

    policy_types = filter_policy_types(policy_types, is_active=filters.get('is_active'))

    # Cut the requested page (?page=, ?page_size=); meta holds the page numbers and totals.
    page, meta = paginate(request, policy_types.order_by('name'))
    serializer = PolicyTypeSerializer(page, many=True)
    return APIResponse(serializer.data, 'Policy types fetched successfully.', meta=meta)


@swagger.policy_type_create
@api_view(['POST'])
@permission_classes([IsAuthenticated, CAN_MANAGE_POLICY_TYPES])
def policy_type_create(request):
    serializer = PolicyTypeCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    name = normalize_name(data['name'])
    ensure_name_free(name)

    with transaction.atomic():
        policy_type = PolicyType.objects.create(
            name=name,
            is_active=data.get('is_active', True),
            created_by=request.user,
            updated_by=request.user,
        )
        # The note lists every field, as the policy type now reads.
        record_note(policy_type, request.user, PolicyTypeNote.KIND_ADDED, diff_snapshots({}, snapshot(policy_type), NOTE_FIELDS))

    return APIResponse(
        PolicyTypeSerializer(policy_type).data,
        'Policy type created successfully.',
        status=status.HTTP_201_CREATED,
    )


@swagger.policy_type_detail
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, CAN_MANAGE_POLICY_TYPES])
def policy_type_detail(request, pk):
    policy_type = get_policy_type_or_404(pk)

    if request.method == 'GET':
        return APIResponse(PolicyTypeSerializer(policy_type).data, 'Policy type fetched successfully.')

    if request.method == 'PATCH':
        # partial=True: only the fields that were sent get updated.
        serializer = PolicyTypeUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields = dict(serializer.validated_data)

        # The name only has to be free when it is actually changing.
        if 'name' in fields:
            fields['name'] = name = normalize_name(fields['name'])
            if name.lower() != policy_type.name.lower():
                ensure_name_free(name, exclude=policy_type)

        before = snapshot(policy_type)
        with transaction.atomic():
            save_policy_type(policy_type, request.user, **fields)
            record_note(policy_type, request.user, PolicyTypeNote.KIND_EDITED, diff_snapshots(before, snapshot(policy_type), NOTE_FIELDS))
        return APIResponse(PolicyTypeSerializer(policy_type).data, 'Policy type updated successfully.')

    # DELETE: soft delete; the name becomes free for reuse.
    policy_type.delete(user=request.user)
    return APIResponse(None, 'Policy type deleted successfully.')


@swagger.policy_type_notes
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_POLICY_TYPES])
def policy_type_notes(request, pk):
    policy_type = get_policy_type_or_404(pk)
    # Newest first (the model's ordering). Not paginated: a policy type has a handful.
    notes = policy_type.notes.select_related('created_by')
    return APIResponse(PolicyTypeNoteSerializer(notes, many=True).data, 'Policy type notes fetched successfully.')
