from django.db import transaction
from django.db.models.functions import Lower
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.base.api.pagination import paginate
from apps.base.api.permissions import module_permission
from apps.base.api.response import APIResponse
from apps.passwords.models import SitePassword, SitePasswordNote
from apps.passwords.utils import (
    SITE_PASSWORD_NOTE_FIELDS,
    diff_snapshots,
    filter_site_passwords,
    get_site_password_or_404,
    record_site_password_note,
    save_password,
    search_site_passwords,
    site_password_snapshot,
)
from apps.passwords.validators import ensure_credentials, ensure_one_party, ensure_site_pair_free

from . import swagger
from .serializers import (
    SitePasswordCreateSerializer,
    SitePasswordListQuerySerializer,
    SitePasswordNoteSerializer,
    SitePasswordSerializer,
    SitePasswordUpdateSerializer,
)

# Site passwords are part of the Passwords module: the same permission guards them.
CAN_MANAGE_PASSWORDS = module_permission('passwords')


def note_changes(before, password):
    """What changed on `password` since the `before` snapshot ({} when new)."""
    return diff_snapshots(before, site_password_snapshot(password), fields=SITE_PASSWORD_NOTE_FIELDS)


@swagger.site_password_list
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_PASSWORDS])
def site_password_list(request):
    # Check the ?search=, ?agent_id=, ?agency_id=, ?site_id= and ?status= values; bad ones give a 400.
    query = SitePasswordListQuerySerializer(data=request.query_params.dict())
    query.is_valid(raise_exception=True)
    filters = query.validated_data

    passwords = SitePassword.objects.select_related('agent', 'agency', 'site')
    search = filters.get('search')
    if search:
        passwords = search_site_passwords(passwords, search)
    passwords = filter_site_passwords(
        passwords,
        agent_id=filters.get('agent_id'),
        agency_id=filters.get('agency_id'),
        site_id=filters.get('site_id'),
        status=filters.get('status'),
    )

    page, meta = paginate(request, passwords.order_by('agent__name', Lower('site__name')))
    return APIResponse(SitePasswordSerializer(page, many=True).data, 'Site passwords fetched successfully.', meta=meta)


@swagger.site_password_create
@api_view(['POST'])
@permission_classes([IsAuthenticated, CAN_MANAGE_PASSWORDS])
def site_password_create(request):
    serializer = SitePasswordCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    agent = data.get('agent')
    agency = data.get('agency')
    ensure_one_party(agent, agency)
    ensure_site_pair_free(data['site'], agent=agent, agency=agency)
    ensure_credentials(data.get('status', 'active'), data.get('username', ''), data.get('portal_password', ''))

    with transaction.atomic():
        password = SitePassword.objects.create(
            agent=agent,
            agency=agency,
            site=data['site'],
            username=data.get('username', ''),
            portal_password=data.get('portal_password', ''),
            status=data.get('status', 'active'),
            created_by=request.user,
            updated_by=request.user,
        )
        # The note lists every filled field; the password only as "set".
        record_site_password_note(password, request.user, SitePasswordNote.KIND_ADDED, note_changes({}, password))

    return APIResponse(
        SitePasswordSerializer(password).data, 'Site password created successfully.', status=status.HTTP_201_CREATED
    )


@swagger.site_password_detail
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, CAN_MANAGE_PASSWORDS])
def site_password_detail(request, pk):
    password = get_site_password_or_404(pk)

    if request.method == 'GET':
        return APIResponse(SitePasswordSerializer(password).data, 'Site password fetched successfully.')

    if request.method == 'PATCH':
        # partial=True: only the fields that were sent get updated.
        serializer = SitePasswordUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields = dict(serializer.validated_data)

        # Choosing an agent clears the agency, and the other way round.
        if fields.get('agent') is not None:
            fields['agency'] = None
        if fields.get('agency') is not None:
            fields['agent'] = None
        agent = fields['agent'] if 'agent' in fields else password.agent
        agency = fields['agency'] if 'agency' in fields else password.agency
        site = fields.get('site', password.site)
        ensure_one_party(agent, agency)

        # The pair only has to be free when it is actually changing.
        if (agent, agency, site) != (password.agent, password.agency, password.site):
            ensure_site_pair_free(site, agent=agent, agency=agency, exclude=password)
        # Checked against the values the password will end up with.
        ensure_credentials(
            fields.get('status', password.status),
            fields.get('username', password.username),
            fields.get('portal_password', password.portal_password),
        )

        before = site_password_snapshot(password)
        with transaction.atomic():
            password = save_password(password, request.user, **fields)
            record_site_password_note(
                password, request.user, SitePasswordNote.KIND_EDITED, note_changes(before, password)
            )
        return APIResponse(SitePasswordSerializer(password).data, 'Site password updated successfully.')

    # DELETE: soft delete; the agent (or agency) + site pair becomes free again.
    password.delete(user=request.user)
    return APIResponse(None, 'Site password deleted successfully.')


@swagger.site_password_notes
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_PASSWORDS])
def site_password_notes(request, pk):
    password = get_site_password_or_404(pk)
    # Newest first (the model's ordering). Not paginated: a password has a handful.
    notes = password.notes.select_related('created_by')
    return APIResponse(SitePasswordNoteSerializer(notes, many=True).data, 'Site password notes fetched successfully.')
