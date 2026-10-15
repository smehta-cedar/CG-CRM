from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.agents.utils import address_text
from apps.base.api.pagination import paginate
from apps.base.api.permissions import ensure_own, module_permission, own_only
from apps.base.api.response import APIResponse
from apps.notifications.services import notify_admins_of_request, notify_agent_of_decision
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
# The Shop's Add files an order; Calendar's Add still can too.
CAN_ORDER_MERCH = module_permission(('requests', 'storefront.shop'))


def get_request_or_404(pk, user=None):
    """With `user`, an agent's sign-in finds only its own requests (404 otherwise)."""
    requests = Request.objects.select_related('agent', 'carrier', 'state', 'product', 'created_by')
    return get_object_or_404(own_only(user, requests) if user else requests, pk=pk)


def _create_agent_request(user, data):
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
        created_by=user,
        updated_by=user,
    )
    notify_admins_of_request(filed, user)
    return filed


@swagger.request_list
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_REQUESTS])
def request_list(request):
    # Check the ?type=, ?status= and ?agent_id= values; bad ones give a 400.
    query = RequestListQuerySerializer(data=request.query_params.dict())
    query.is_valid(raise_exception=True)
    filters = query.validated_data

    requests = own_only(request.user, Request.objects.select_related('agent', 'carrier', 'state', 'product', 'created_by'))
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
    ensure_own(request.user, serializer.validated_data['agent'].pk)
    filed = _create_agent_request(request.user, serializer.validated_data)
    return APIResponse(RequestSerializer(filed).data, 'Request filed successfully.', status=status.HTTP_201_CREATED)


@swagger.request_merch_create
@api_view(['POST'])
@permission_classes([IsAuthenticated, CAN_ORDER_MERCH])
def request_merch_create(request):
    """A tee order from the dashboard shop. Buyer contact comes from the
    signed-in user; a linked agent's home address is used when present."""
    serializer = MerchRequestCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    user = request.user
    agent = user.agent if user.agent_id else None
    product = data['product']
    size = data['size'].strip()
    color = ensure_order_fits(product, data['color'].strip().lower(), size, data['quantity'])
    filed = Request.objects.create(
        type='merch',
        # An agent's own order lands on their Calendar.
        agent=agent,
        product=product,
        buyer_name=' '.join(user.full_name.split()),
        email=user.email.strip().lower(),
        phone=user.phone.strip(),
        address=address_text(agent) if agent else '',
        size=size,
        color=color['label'],
        quantity=data['quantity'],
        note=data.get('note', '').strip(),
        created_by=user,
        updated_by=user,
    )
    notify_admins_of_request(filed, user)
    return APIResponse(RequestSerializer(filed).data, 'Order filed successfully.', status=status.HTTP_201_CREATED)


@swagger.request_detail
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, CAN_MANAGE_REQUESTS])
def request_detail(request, pk):
    filed = get_request_or_404(pk, request.user)

    if request.method == 'GET':
        return APIResponse(RequestSerializer(filed).data, 'Request fetched successfully.')

    if request.method == 'PATCH':
        # partial=True: only the fields that were sent get updated.
        serializer = RequestUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields = dict(serializer.validated_data)
        if 'note' in fields:
            fields['note'] = fields['note'].strip()
        previous_status = filed.status
        for name, value in fields.items():
            setattr(filed, name, value)
        filed.updated_by = request.user
        filed.save(update_fields=[*fields, 'updated_by'])
        if 'status' in fields:
            notify_agent_of_decision(filed, request.user, previous_status)
        return APIResponse(RequestSerializer(filed).data, 'Request updated successfully.')

    # DELETE: soft delete.
    filed.delete(user=request.user)
    return APIResponse(None, 'Request deleted successfully.')
