from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.base.api.pagination import paginate
from apps.base.api.permissions import module_permission
from apps.base.api.response import APIResponse
from apps.notifications.services import notify_admins_of_request
from apps.requests.models import Request
from apps.requests.validators import ensure_fields_for_type, resolve_state
from apps.storefront.validators import ensure_order_fits

from . import swagger
from .serializers import (
    MerchRequestCreateSerializer,
    RequestCreateSerializer,
    RequestListQuerySerializer,
    RequestSerializer,
    RequestUpdateSerializer,
)

CAN_MANAGE_REQUESTS = module_permission('requests')


def get_request_or_404(pk):
    return get_object_or_404(Request.objects.select_related('agent', 'carrier', 'state', 'product', 'created_by'), pk=pk)


@swagger.request_list
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_REQUESTS])
def request_list(request):
    # Check the ?type=, ?status= and ?agent_id= values; bad ones give a 400.
    query = RequestListQuerySerializer(data=request.query_params.dict())
    query.is_valid(raise_exception=True)
    filters = query.validated_data

    requests = Request.objects.select_related('agent', 'carrier', 'state', 'product', 'created_by')
    if filters.get('type'):
        requests = requests.filter(type=filters['type'])
    if filters.get('status'):
        requests = requests.filter(status=filters['status'])
    if filters.get('agent_id'):
        requests = requests.filter(agent_id=filters['agent_id'])

    # Oldest first (the model's ordering); meta holds the page numbers and totals.
    page, meta = paginate(request, requests)
    return APIResponse(RequestSerializer(page, many=True).data, 'Requests fetched successfully.', meta=meta)


@swagger.request_create
@api_view(['POST'])
@permission_classes([IsAuthenticated, CAN_MANAGE_REQUESTS])
def request_create(request):
    serializer = RequestCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    ensure_fields_for_type(data)
    is_placement = data['type'] in ('licensing', 'contract')
    filed = Request.objects.create(
        type=data['type'],
        agent=data['agent'],
        carrier=data.get('carrier') if is_placement else None,
        state=resolve_state(data['state']) if is_placement else None,
        start_date=data.get('start_date') if data['type'] == 'day_off' else None,
        end_date=data.get('end_date') if data['type'] == 'day_off' else None,
        note=data.get('note', '').strip(),
        created_by=request.user,
        updated_by=request.user,
    )
    notify_admins_of_request(filed, request.user)
    return APIResponse(RequestSerializer(filed).data, 'Request filed successfully.', status=status.HTTP_201_CREATED)


@swagger.request_merch_create
@api_view(['POST'])
@permission_classes([IsAuthenticated, CAN_MANAGE_REQUESTS])
def request_merch_create(request):
    """A tee order from the public shop. The shop has no sign-in, so the Next
    server posts this as the shop's own service account (see seed_requests)."""
    serializer = MerchRequestCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    product = data['product']
    size = data['size'].strip()
    color = ensure_order_fits(product, data['color'].strip().lower(), size, data['quantity'])
    filed = Request.objects.create(
        type='merch',
        product=product,
        buyer_name=' '.join(data['buyer_name'].split()),
        email=data['email'].strip().lower(),
        phone=data['phone'].strip(),
        address=data['address'].strip(),
        size=size,
        color=color['label'],
        quantity=data['quantity'],
        note=data.get('note', '').strip(),
        created_by=request.user,
        updated_by=request.user,
    )
    return APIResponse(RequestSerializer(filed).data, 'Order filed successfully.', status=status.HTTP_201_CREATED)


@swagger.request_detail
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, CAN_MANAGE_REQUESTS])
def request_detail(request, pk):
    filed = get_request_or_404(pk)

    if request.method == 'GET':
        return APIResponse(RequestSerializer(filed).data, 'Request fetched successfully.')

    if request.method == 'PATCH':
        # partial=True: only the fields that were sent get updated.
        serializer = RequestUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields = dict(serializer.validated_data)
        if 'note' in fields:
            fields['note'] = fields['note'].strip()
        for name, value in fields.items():
            setattr(filed, name, value)
        filed.updated_by = request.user
        filed.save(update_fields=[*fields, 'updated_by'])
        return APIResponse(RequestSerializer(filed).data, 'Request updated successfully.')

    # DELETE: soft delete.
    filed.delete(user=request.user)
    return APIResponse(None, 'Request deleted successfully.')
