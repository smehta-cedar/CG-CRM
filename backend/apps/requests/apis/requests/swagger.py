"""Swagger docs for the requests endpoints, one per view in views.py."""
from drf_spectacular.utils import extend_schema

from apps.base.api.schema import (
    PAGINATION_PARAMETERS,
    api_response,
    combine_schemas,
    error_responses,
)

from .serializers import (
    MerchRequestCreateSerializer,
    RequestCreateSerializer,
    RequestListQuerySerializer,
    RequestSerializer,
    RequestUpdateSerializer,
)

TAGS = ['Requests']


request_list = extend_schema(
    operation_id='requests_list',
    tags=TAGS,
    summary='List requests',
    description='Every HR request, oldest first: agent requests and tee orders from the shop.',
    parameters=[RequestListQuerySerializer, *PAGINATION_PARAMETERS],
    responses={200: api_response(RequestSerializer, paginated=True), **error_responses(400, 401, 403)},
)


request_create = extend_schema(
    operation_id='requests_create',
    tags=TAGS,
    summary="File an agent's request",
    description=(
        'licensing and contract need `state` and `carrier_id`; day_off needs `start_date` and '
        '`end_date` (inclusive, last on or after first). Starts pending.'
    ),
    request=RequestCreateSerializer,
    responses={201: api_response(RequestSerializer), **error_responses(400, 401, 403)},
)


request_merch_create = extend_schema(
    operation_id='requests_merch_create',
    tags=TAGS,
    summary='File a tee order from the shop',
    description="Posted by the shop's service account on behalf of a visitor. Starts pending.",
    request=MerchRequestCreateSerializer,
    responses={201: api_response(RequestSerializer), **error_responses(400, 401, 403)},
)


request_detail = combine_schemas(
    extend_schema(
        methods=['GET'],
        tags=TAGS,
        summary='Get a request',
        responses={200: api_response(RequestSerializer), **error_responses(401, 403, 404)},
    ),
    extend_schema(
        methods=['PATCH'],
        tags=TAGS,
        summary="Set a request's status or note",
        request=RequestUpdateSerializer,
        responses={200: api_response(RequestSerializer), **error_responses(400, 401, 403, 404)},
    ),
    extend_schema(
        methods=['DELETE'],
        tags=TAGS,
        summary='Delete a request',
        description='Soft delete: the request is hidden and can be restored.',
        responses={200: api_response(), **error_responses(401, 403, 404)},
    ),
)
