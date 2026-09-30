from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.base.api.pagination import paginate
from apps.base.api.permissions import module_permission
from apps.base.api.response import APIResponse
from apps.contracts.validators import ensure_carrier_accessible
from apps.passwords.models import Password, PasswordNote
from apps.passwords.utils import (
    diff_snapshots,
    filter_passwords,
    get_password_or_404,
    record_note,
    save_password,
    search_passwords,
    snapshot,
)
from apps.passwords.validators import ensure_one_party, ensure_pair_free, ensure_password_not_blank

from . import swagger
from .serializers import (
    PasswordCreateSerializer,
    PasswordListQuerySerializer,
    PasswordNoteSerializer,
    PasswordSerializer,
    PasswordUpdateSerializer,
)

CAN_MANAGE_PASSWORDS = module_permission('passwords')


@swagger.password_list
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_PASSWORDS])
def password_list(request):
    # Check the ?search=, ?agent_id=, ?agency_id=, ?carrier_id= and ?status= values; bad ones give a 400.
    query = PasswordListQuerySerializer(data=request.query_params.dict())
    query.is_valid(raise_exception=True)
    filters = query.validated_data

    passwords = Password.objects.select_related('agent', 'agency', 'carrier')

    search = filters.get('search')
    if search:
        passwords = search_passwords(passwords, search)

    passwords = filter_passwords(
        passwords,
        agent_id=filters.get('agent_id'),
        agency_id=filters.get('agency_id'),
        carrier_id=filters.get('carrier_id'),
        status=filters.get('status'),
    )

    # Cut the requested page (?page=, ?page_size=); meta holds the page numbers and totals.
    page, meta = paginate(request, passwords.order_by('agent__name', 'carrier__name'))
    serializer = PasswordSerializer(page, many=True)
    return APIResponse(serializer.data, 'Passwords fetched successfully.', meta=meta)


@swagger.password_create
@api_view(['POST'])
@permission_classes([IsAuthenticated, CAN_MANAGE_PASSWORDS])
def password_create(request):
    serializer = PasswordCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    agent = data.get('agent')
    agency = data.get('agency')
    ensure_one_party(agent, agency)
    # An agent needs the carrier open to agents; the agency's own login doesn't.
    if agent is not None:
        ensure_carrier_accessible(data['carrier'])
    ensure_pair_free(data['carrier'], agent=agent, agency=agency)
    ensure_password_not_blank(data['portal_password'])

    with transaction.atomic():
        password = Password.objects.create(
            agent=agent,
            agency=agency,
            carrier=data['carrier'],
            username=data['username'],
            portal_password=data['portal_password'],
            link=data.get('link', ''),
            status=data.get('status', 'active'),
            created_by=request.user,
            updated_by=request.user,
        )
        # The note lists every filled field; the password only as "set".
        record_note(password, request.user, PasswordNote.KIND_ADDED, diff_snapshots({}, snapshot(password)))

    return APIResponse(PasswordSerializer(password).data, 'Password created successfully.', status=status.HTTP_201_CREATED)


@swagger.password_detail
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, CAN_MANAGE_PASSWORDS])
def password_detail(request, pk):
    password = get_password_or_404(pk)

    if request.method == 'GET':
        return APIResponse(PasswordSerializer(password).data, 'Password fetched successfully.')

    if request.method == 'PATCH':
        # partial=True: only the fields that were sent get updated.
        serializer = PasswordUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields = dict(serializer.validated_data)

        # Choosing an agent clears the agency, and the other way round.
        if fields.get('agent') is not None:
            fields['agency'] = None
        if fields.get('agency') is not None:
            fields['agent'] = None
        agent = fields['agent'] if 'agent' in fields else password.agent
        agency = fields['agency'] if 'agency' in fields else password.agency
        carrier = fields.get('carrier', password.carrier)
        ensure_one_party(agent, agency)

        # An agent at a carrier new to them needs it open to agents; keeping it doesn't.
        if agent is not None and (carrier != password.carrier or password.agent is None):
            ensure_carrier_accessible(carrier)
        # The pair only has to be free when it is actually changing.
        if (agent, agency, carrier) != (password.agent, password.agency, password.carrier):
            ensure_pair_free(carrier, agent=agent, agency=agency, exclude=password)

        if 'portal_password' in fields:
            ensure_password_not_blank(fields['portal_password'])

        before = snapshot(password)
        with transaction.atomic():
            password = save_password(password, request.user, **fields)
            record_note(password, request.user, PasswordNote.KIND_EDITED, diff_snapshots(before, snapshot(password)))
        return APIResponse(PasswordSerializer(password).data, 'Password updated successfully.')

    # DELETE: soft delete; the agent (or agency) + carrier pair becomes free again.
    password.delete(user=request.user)
    return APIResponse(None, 'Password deleted successfully.')


@swagger.password_notes
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_PASSWORDS])
def password_notes(request, pk):
    password = get_password_or_404(pk)
    # Newest first (the model's ordering). Not paginated: a password has a handful.
    notes = password.notes.select_related('created_by')
    return APIResponse(PasswordNoteSerializer(notes, many=True).data, 'Password notes fetched successfully.')
