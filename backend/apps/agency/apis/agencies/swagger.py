"""Swagger docs for the agencies endpoints, one per view in views.py."""
from drf_spectacular.utils import extend_schema

from apps.base.api.schema import (
    PAGINATION_PARAMETERS,
    api_response,
    combine_schemas,
    error_responses,
)

from .serializers import (
    AgencyCreateSerializer,
    AgencyListQuerySerializer,
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
