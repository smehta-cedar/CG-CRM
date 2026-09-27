from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.agency.models import Agency, AgencyNote
from apps.agency.utils import (
    diff_snapshots,
    filter_agencies,
    get_agency_or_404,
    normalize_email,
    normalize_name,
    normalize_npn,
    record_note,
    save_agency,
    search_agencies,
    snapshot,
    sync_licenses,
)
from apps.agency.validators import ensure_name_free, ensure_npn_free, resolve_licenses
from apps.base.api.pagination import paginate
from apps.base.api.permissions import module_permission
from apps.base.api.response import APIResponse

from . import swagger
from .serializers import (
    AgencyCreateSerializer,
    AgencyListQuerySerializer,
    AgencyNoteSerializer,
    AgencySerializer,
    AgencyUpdateSerializer,
)

CAN_MANAGE_AGENCIES = module_permission('agencies')


@swagger.agency_list
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_AGENCIES])
def agency_list(request):
    # Check the ?search= and ?is_active= values; bad ones give a 400.
    query = AgencyListQuerySerializer(data=request.query_params.dict())
    query.is_valid(raise_exception=True)
    filters = query.validated_data

    agencies = Agency.objects.prefetch_related('licenses__state')

    search = filters.get('search')
    if search:
        agencies = search_agencies(agencies, search)

    agencies = filter_agencies(
        agencies,
        is_active=filters.get('is_active'),
    )

    # Cut the requested page (?page=, ?page_size=); meta holds the page numbers and totals.
    page, meta = paginate(request, agencies)
    serializer = AgencySerializer(page, many=True)
    return APIResponse(serializer.data, 'Agencies fetched successfully.', meta=meta)


@swagger.agency_create
@api_view(['POST'])
@permission_classes([IsAuthenticated, CAN_MANAGE_AGENCIES])
def agency_create(request):
    serializer = AgencyCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    name = normalize_name(data['name'])
    npn = normalize_npn(data.get('npn', ''))
    ensure_name_free(name)
    ensure_npn_free(npn)
    licenses = resolve_licenses(data.get('licenses', []))

    with transaction.atomic():
        agency = Agency.objects.create(
            name=name,
            aliases=data.get('aliases', []),
            is_active=data.get('is_active', True),
            npn=npn,
            email=normalize_email(data.get('email', '')),
            phone=data.get('phone', ''),
            created_by=request.user,
            updated_by=request.user,
        )
        sync_licenses(agency, request.user, licenses)
        agency = get_agency_or_404(agency.pk)
        # The note lists every filled field, as the agency now reads.
        record_note(agency, request.user, AgencyNote.KIND_ADDED, diff_snapshots({}, snapshot(agency)))
    return APIResponse(AgencySerializer(agency).data, 'Agency created successfully.', status=status.HTTP_201_CREATED)


@swagger.agency_detail
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, CAN_MANAGE_AGENCIES])
def agency_detail(request, pk):
    agency = get_agency_or_404(pk)

    if request.method == 'GET':
        return APIResponse(AgencySerializer(agency).data, 'Agency fetched successfully.')

    if request.method == 'PATCH':
        # partial=True: only the fields that were sent get updated.
        serializer = AgencyUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields = dict(serializer.validated_data)

        # The name and NPN only have to be free when they are actually changing.
        if 'name' in fields:
            fields['name'] = normalize_name(fields['name'])
            if fields['name'].lower() != agency.name.lower():
                ensure_name_free(fields['name'], exclude=agency)

        if 'npn' in fields:
            fields['npn'] = normalize_npn(fields['npn'])
            if fields['npn'] != agency.npn:
                ensure_npn_free(fields['npn'], exclude=agency)

        if 'email' in fields:
            fields['email'] = normalize_email(fields['email'])

        licenses = None
        if 'licenses' in fields:
            licenses = resolve_licenses(fields.pop('licenses'))

        before = snapshot(agency)
        with transaction.atomic():
            if fields:
                save_agency(agency, request.user, **fields)
            if licenses is not None:
                sync_licenses(agency, request.user, licenses)
            # Read the rows again for the note and the response.
            agency = get_agency_or_404(pk)
            record_note(agency, request.user, AgencyNote.KIND_EDITED, diff_snapshots(before, snapshot(agency)))
        return APIResponse(AgencySerializer(agency).data, 'Agency updated successfully.')

    # DELETE: soft delete; the name and NPN become free for reuse.
    agency.delete(user=request.user)
    return APIResponse(None, 'Agency deleted successfully.')


@swagger.agency_notes
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_AGENCIES])
def agency_notes(request, pk):
    agency = get_agency_or_404(pk)
    # Newest first (the model's ordering). Not paginated: an agency has a handful.
    notes = agency.notes.select_related('created_by')
    return APIResponse(AgencyNoteSerializer(notes, many=True).data, 'Agency notes fetched successfully.')
