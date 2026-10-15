"""Swagger docs for the agencies endpoints, one per view in views.py."""
from drf_spectacular.utils import extend_schema

from apps.base.api.schema import (
    PAGINATION_PARAMETERS,
    api_response,
    combine_schemas,
    error_responses,
)

from .serializers import (
    AgencyCommentCreateSerializer,
    AgencyCommentSerializer,
    AgencyCreateSerializer,
    AgencyListQuerySerializer,
    AgencyNoteSerializer,
    AgencySerializer,
    AgencyUpdateSerializer,
)

TAGS = ['Agencies']


agency_list = extend_schema(
    operation_id='agencies_list',
    tags=TAGS,
    summary='List agencies',
    parameters=[AgencyListQuerySerializer, *PAGINATION_PARAMETERS],
    responses={200: api_response(AgencySerializer, paginated=True), **error_responses(400, 401, 403)},
)


agency_create = extend_schema(
    operation_id='agencies_create',
    tags=TAGS,
    summary='Create an agency',
    description='Records an "added" note. `licenses` creates one licence row per state: active unless a `status` is given, and starting today and running two years unless `start_date` / `end_date` are given.',
    request=AgencyCreateSerializer,
    responses={201: api_response(AgencySerializer), **error_responses(400, 401, 403)},
)


agency_detail = combine_schemas(
    extend_schema(
        methods=['GET'],
        tags=TAGS,
        summary='Get an agency',
        responses={200: api_response(AgencySerializer), **error_responses(401, 403, 404)},
    ),
    extend_schema(
        methods=['PATCH'],
        tags=TAGS,
        summary='Update an agency',
        description='Records an "edited" note when something changed. `licenses` replaces the set of licensed states; a row\'s `status`, `start_date` and `end_date` are set when given and kept when left out. `agent_licenses` gives agents a pending licence in a state; already licensed ones are skipped.',
        request=AgencyUpdateSerializer,
        responses={200: api_response(AgencySerializer), **error_responses(400, 401, 403, 404)},
    ),
    extend_schema(
        methods=['DELETE'],
        tags=TAGS,
        summary='Delete an agency',
        description='Soft delete: the agency is hidden and can be restored.',
        responses={200: api_response(), **error_responses(401, 403, 404)},
    ),
)


agency_notes = extend_schema(
    operation_id='agencies_notes',
    tags=TAGS,
    summary="List an agency's change notes",
    description='Newest first. Not paginated.',
    responses={200: api_response(AgencyNoteSerializer, many=True), **error_responses(401, 403, 404)},
)


agency_comments = combine_schemas(
    extend_schema(
        methods=['GET'],
        operation_id='agencies_comments_list',
        tags=TAGS,
        summary="List an agency's written notes",
        description='Newest first. Not paginated. The change log is notes/.',
        responses={200: api_response(AgencyCommentSerializer, many=True), **error_responses(401, 403, 404)},
    ),
    extend_schema(
        methods=['POST'],
        operation_id='agencies_comments_create',
        tags=TAGS,
        summary='Write a note on an agency',
        description='Needs agencies update.',
        request=AgencyCommentCreateSerializer,
        responses={201: api_response(AgencyCommentSerializer), **error_responses(400, 401, 403, 404)},
    ),
)


agency_comment_delete = extend_schema(
    operation_id='agencies_comments_delete',
    tags=TAGS,
    summary='Delete a written note',
    description='Soft delete. Needs agencies update.',
    responses={200: api_response(), **error_responses(401, 403, 404)},
)
