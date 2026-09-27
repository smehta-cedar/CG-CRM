from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.agents.models import Agent, AgentNote
from apps.agents.utils import (
    address_fields,
    diff_snapshots,
    filter_agents,
    get_agent_or_404,
    normalize_email,
    normalize_name,
    normalize_npn,
    record_note,
    save_agent,
    search_agents,
    snapshot,
    sync_licenses,
)
from apps.agents.validators import (
    ensure_address_complete,
    ensure_name_free,
    ensure_npn_free,
    resolve_licenses,
    resolve_state,
)
from apps.base.api.pagination import paginate
from apps.base.api.permissions import module_permission
from apps.base.api.response import APIResponse

from . import swagger
from .serializers import (
    AgentCreateSerializer,
    AgentListQuerySerializer,
    AgentNoteSerializer,
    AgentSerializer,
    AgentUpdateSerializer,
)

CAN_MANAGE_AGENTS = module_permission('agents')


def _address_columns(address):
    """The address_* columns for a request's address, once it is checked."""
    ensure_address_complete(address)
    if address and (address.get('street') or '').strip():
        resolve_state(address['state'], 'address')
        return address_fields(address)
    return address_fields(None)


@swagger.agent_list
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_AGENTS])
def agent_list(request):
    # Check the ?search=, ?is_active= and ?state= values; bad ones give a 400.
    query = AgentListQuerySerializer(data=request.query_params.dict())
    query.is_valid(raise_exception=True)
    filters = query.validated_data

    agents = Agent.objects.prefetch_related('licenses__state')

    search = filters.get('search')
    if search:
        agents = search_agents(agents, search)

    agents = filter_agents(
        agents,
        is_active=filters.get('is_active'),
        state=filters.get('state'),
    )

    # Cut the requested page (?page=, ?page_size=); meta holds the page numbers and totals.
    page, meta = paginate(request, agents.order_by('name'))
    serializer = AgentSerializer(page, many=True)
    return APIResponse(serializer.data, 'Agents fetched successfully.', meta=meta)


@swagger.agent_create
@api_view(['POST'])
@permission_classes([IsAuthenticated, CAN_MANAGE_AGENTS])
def agent_create(request):
    serializer = AgentCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    name = normalize_name(data['name'])
    npn = normalize_npn(data['npn'])
    ensure_name_free(name)
    ensure_npn_free(npn)
    address = _address_columns(data.get('address'))
    licenses = resolve_licenses(data.get('licenses', []))

    with transaction.atomic():
        agent = Agent.objects.create(
            name=name,
            aliases=data.get('aliases', []),
            npn=npn,
            email=normalize_email(data.get('email', '')),
            phone=data.get('phone', '').strip(),
            personal_email=normalize_email(data.get('personal_email', '')),
            personal_phone=data.get('personal_phone', '').strip(),
            is_active=data.get('is_active', True),
            created_by=request.user,
            updated_by=request.user,
            **address,
        )
        sync_licenses(agent, request.user, licenses)
        agent = get_agent_or_404(agent.pk)
        # The note lists every filled field, as the agent now reads.
        record_note(agent, request.user, AgentNote.KIND_ADDED, diff_snapshots({}, snapshot(agent)))

    return APIResponse(AgentSerializer(agent).data, 'Agent created successfully.', status=status.HTTP_201_CREATED)


@swagger.agent_detail
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, CAN_MANAGE_AGENTS])
def agent_detail(request, pk):
    agent = get_agent_or_404(pk)

    if request.method == 'GET':
        return APIResponse(AgentSerializer(agent).data, 'Agent fetched successfully.')

    if request.method == 'PATCH':
        # partial=True: only the fields that were sent get updated.
        serializer = AgentUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields = dict(serializer.validated_data)

        # The name and NPN only have to be free when they are actually changing.
        if 'name' in fields:
            fields['name'] = normalize_name(fields['name'])
            if fields['name'].lower() != agent.name.lower():
                ensure_name_free(fields['name'], exclude=agent)

        if 'npn' in fields:
            fields['npn'] = normalize_npn(fields['npn'])
            if fields['npn'] != agent.npn:
                ensure_npn_free(fields['npn'], exclude=agent)

        for field in ('email', 'personal_email'):
            if field in fields:
                fields[field] = normalize_email(fields[field])
        for field in ('phone', 'personal_phone'):
            if field in fields:
                fields[field] = fields[field].strip()

        if 'address' in fields:
            fields.update(_address_columns(fields.pop('address')))

        licenses = None
        if 'licenses' in fields:
            licenses = resolve_licenses(fields.pop('licenses'))

        before = snapshot(agent)
        with transaction.atomic():
            if fields:
                save_agent(agent, request.user, **fields)
            if licenses is not None:
                sync_licenses(agent, request.user, licenses)
            # Read the rows again for the note and the response.
            agent = get_agent_or_404(pk)
            record_note(agent, request.user, AgentNote.KIND_EDITED, diff_snapshots(before, snapshot(agent)))
        return APIResponse(AgentSerializer(agent).data, 'Agent updated successfully.')

    # DELETE: soft delete; the name and NPN become free for reuse.
    agent.delete(user=request.user)
    return APIResponse(None, 'Agent deleted successfully.')


@swagger.agent_notes
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_AGENTS])
def agent_notes(request, pk):
    agent = get_agent_or_404(pk)
    # Newest first (the model's ordering). Not paginated: an agent has a handful.
    notes = agent.notes.select_related('created_by')
    return APIResponse(AgentNoteSerializer(notes, many=True).data, 'Agent notes fetched successfully.')
