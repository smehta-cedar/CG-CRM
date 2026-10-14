"""Swagger docs for the site password endpoints, one per view in views.py."""
from drf_spectacular.utils import extend_schema

from apps.base.api.schema import PAGINATION_PARAMETERS, api_response, combine_schemas, error_responses

from .serializers import (
    SitePasswordCreateSerializer,
    SitePasswordListQuerySerializer,
    SitePasswordNoteSerializer,
    SitePasswordSerializer,
    SitePasswordUpdateSerializer,
)

TAGS = ['Site passwords']


site_password_list = extend_schema(
    operation_id='site_passwords_list',
    tags=TAGS,
    summary='List site passwords',
    description="Portal logins at sites (not carriers), agents' and the agency's own, by agent name then site name.",
    parameters=[SitePasswordListQuerySerializer, *PAGINATION_PARAMETERS],
    responses={200: api_response(SitePasswordSerializer, paginated=True), **error_responses(400, 401, 403)},
)


site_password_create = extend_schema(
    operation_id='site_passwords_create',
    tags=TAGS,
    summary='Create a site password',
    description=(
        'For an agent (agent_id) or the agency (agency_id) at a site (site_id). One per agent at each site, '
        'and one for the agency. Records an "added" note; the password only as "set".'
    ),
    request=SitePasswordCreateSerializer,
    responses={201: api_response(SitePasswordSerializer), **error_responses(400, 401, 403)},
)


site_password_detail = combine_schemas(
    extend_schema(
        methods=['GET'],
        tags=TAGS,
        summary='Get a site password',
        responses={200: api_response(SitePasswordSerializer), **error_responses(401, 403, 404)},
    ),
    extend_schema(
        methods=['PATCH'],
        tags=TAGS,
        summary='Update a site password',
        description='Records an "edited" note when something changed; the password only as "changed".',
        request=SitePasswordUpdateSerializer,
        responses={200: api_response(SitePasswordSerializer), **error_responses(400, 401, 403, 404)},
    ),
    extend_schema(
        methods=['DELETE'],
        tags=TAGS,
        summary='Delete a site password',
        description='Soft delete: the password is hidden and can be restored.',
        responses={200: api_response(), **error_responses(401, 403, 404)},
    ),
)


site_password_notes = extend_schema(
    operation_id='site_passwords_notes',
    tags=TAGS,
    summary="List a site password's change notes",
    description='Newest first. Not paginated. The password value is never in a note.',
    responses={200: api_response(SitePasswordNoteSerializer, many=True), **error_responses(401, 403, 404)},
)
