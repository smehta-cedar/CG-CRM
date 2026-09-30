from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.base.api.pagination import paginate
from apps.base.api.permissions import module_permission
from apps.base.api.response import APIResponse
from apps.carriers.models import Carrier, CarrierNote
from apps.carriers.utils import (
    diff_snapshots,
    filter_carriers,
    get_carrier_or_404,
    normalize_name,
    record_note,
    save_carrier,
    search_carriers,
    snapshot,
    sync_licenses,
)
from apps.carriers.validators import (
    ensure_aliases_free,
    ensure_lines_chosen,
    ensure_name_free,
    resolve_licenses,
)
from apps.contracts.utils import with_agent_access

from . import swagger
from .serializers import (
    CarrierCreateSerializer,
    CarrierListQuerySerializer,
    CarrierNoteSerializer,
    CarrierSerializer,
    CarrierUpdateSerializer,
)

CAN_MANAGE_CARRIERS = module_permission('carriers')


@swagger.carrier_list
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_CARRIERS])
def carrier_list(request):
    # Check the ?search=, ?is_active= and ?state= values; bad ones give a 400.
    query = CarrierListQuerySerializer(data=request.query_params.dict())
    query.is_valid(raise_exception=True)
    filters = query.validated_data

    # agent_accessible in one query rather than one per carrier.
    carriers = with_agent_access(Carrier.objects.prefetch_related('available_states', 'licenses__state'))

    search = filters.get('search')
    if search:
        carriers = search_carriers(carriers, search)

    carriers = filter_carriers(
        carriers,
        is_active=filters.get('is_active'),
        state=filters.get('state'),
    )

    # Cut the requested page (?page=, ?page_size=); meta holds the page numbers and totals.
    page, meta = paginate(request, carriers.order_by('name'))
    serializer = CarrierSerializer(page, many=True)
    return APIResponse(serializer.data, 'Carriers fetched successfully.', meta=meta)


@swagger.carrier_create
@api_view(['POST'])
@permission_classes([IsAuthenticated, CAN_MANAGE_CARRIERS])
def carrier_create(request):
    serializer = CarrierCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    name = normalize_name(data['name'])
    aliases = data.get('aliases', [])
    lines = data['lines_of_business']
    ensure_name_free(name)
    ensure_aliases_free(aliases, name)
    ensure_lines_chosen(lines)
    licenses = resolve_licenses(data.get('licenses', []))

    with transaction.atomic():
        carrier = Carrier.objects.create(
            name=name,
            aliases=aliases,
            lines_of_business=lines,
            link=data.get('link', ''),
            status=data.get('status', 'active'),
            created_by=request.user,
            updated_by=request.user,
        )
        sync_licenses(carrier, request.user, licenses)
        # The note lists every filled field, as the carrier now reads.
        carrier = get_carrier_or_404(carrier.pk)
        record_note(carrier, request.user, CarrierNote.KIND_ADDED, diff_snapshots({}, snapshot(carrier)))

    return APIResponse(CarrierSerializer(carrier).data, 'Carrier created successfully.', status=status.HTTP_201_CREATED)


@swagger.carrier_detail
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, CAN_MANAGE_CARRIERS])
def carrier_detail(request, pk):
    carrier = get_carrier_or_404(pk)

    if request.method == 'GET':
        return APIResponse(CarrierSerializer(carrier).data, 'Carrier fetched successfully.')

    if request.method == 'PATCH':
        # partial=True: only the fields that were sent get updated.
        serializer = CarrierUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields = dict(serializer.validated_data)

        # The name only has to be free when it is actually changing.
        name = carrier.name
        if 'name' in fields:
            fields['name'] = name = normalize_name(fields['name'])
            if name.lower() != carrier.name.lower():
                ensure_name_free(name, exclude=carrier)

        if 'aliases' in fields:
            ensure_aliases_free(fields['aliases'], name, exclude=carrier)

        if 'lines_of_business' in fields:
            ensure_lines_chosen(fields['lines_of_business'])

        licenses = None
        if 'licenses' in fields:
            licenses = resolve_licenses(fields.pop('licenses'))

        before = snapshot(carrier)
        with transaction.atomic():
            save_carrier(carrier, request.user, licenses=licenses, **fields)
            # The state rows were just replaced; read them again for the note and the response.
            carrier = get_carrier_or_404(pk)
            record_note(carrier, request.user, CarrierNote.KIND_EDITED, diff_snapshots(before, snapshot(carrier)))
        return APIResponse(CarrierSerializer(carrier).data, 'Carrier updated successfully.')

    # DELETE: soft delete; the name becomes free for reuse.
    carrier.delete(user=request.user)
    return APIResponse(None, 'Carrier deleted successfully.')


@swagger.carrier_notes
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_CARRIERS])
def carrier_notes(request, pk):
    carrier = get_carrier_or_404(pk)
    # Newest first (the model's ordering). Not paginated: a carrier has a handful.
    notes = carrier.notes.select_related('created_by')
    return APIResponse(CarrierNoteSerializer(notes, many=True).data, 'Carrier notes fetched successfully.')
