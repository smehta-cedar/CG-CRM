"""Swagger docs for the agents endpoints, one per view in views.py."""
from drf_spectacular.utils import extend_schema

from apps.base.api.schema import (
    PAGINATION_PARAMETERS,
    api_response,
    combine_schemas,
    error_responses,
)

from .serializers import (
    AgentCreateSerializer,
    AgentListQuerySerializer,
    AgentNoteSerializer,
    AgentSerializer,
    AgentUpdateSerializer,
)

TAGS = ['Agents']


agent_list = extend_schema(
    operation_id='agents_list',
    tags=TAGS,
    summary='List agents',
    parameters=[AgentListQuerySerializer, *PAGINATION_PARAMETERS],
    responses={200: api_response(AgentSerializer, paginated=True), **error_responses(400, 401, 403)},
)


agent_create = extend_schema(
    operation_id='agents_create',
    tags=TAGS,
    summary='Create an agent',
    description=(
        'Records an "added" note listing every filled field. `licenses` creates one '
        'active licence row per state, starting today and running two years.'
    ),
    request=AgentCreateSerializer,
    responses={201: api_response(AgentSerializer), **error_responses(400, 401, 403)},
)


agent_detail = combine_schemas(
    extend_schema(
        methods=['GET'],
        tags=TAGS,
        summary='Get an agent',
        responses={200: api_response(AgentSerializer), **error_responses(401, 403, 404)},
    ),
    extend_schema(
        methods=['PATCH'],
        tags=TAGS,
        summary='Update an agent',
        description=(
            'Records an "edited" note when something changed. `licenses` replaces the set: a '
            'listed state keeps its row (number as given), an unlisted one loses its row, a '
            'new one gets an active row starting today.'
        ),
        request=AgentUpdateSerializer,
        responses={200: api_response(AgentSerializer), **error_responses(400, 401, 403, 404)},
    ),
    extend_schema(
        methods=['DELETE'],
        tags=TAGS,
        summary='Delete an agent',
        description='Soft delete: the agent is hidden and can be restored.',
        responses={200: api_response(), **error_responses(401, 403, 404)},
    ),
)


agent_notes = extend_schema(
    operation_id='agents_notes',
    tags=TAGS,
    summary="List an agent's change notes",
    description='Newest first. Not paginated.',
    responses={200: api_response(AgentNoteSerializer, many=True), **error_responses(401, 403, 404)},
)
