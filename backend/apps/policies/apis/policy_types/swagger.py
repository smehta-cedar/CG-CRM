"""Swagger docs for the policy type endpoints, one per view in views.py."""
from drf_spectacular.utils import extend_schema

from apps.base.api.schema import (
    PAGINATION_PARAMETERS,
    api_response,
    combine_schemas,
    error_responses,
)

from .serializers import (
    PolicyTypeCreateSerializer,
    PolicyTypeListQuerySerializer,
    PolicyTypeNoteSerializer,
    PolicyTypeSerializer,
    PolicyTypeUpdateSerializer,
)

TAGS = ['Policy types']


policy_type_list = extend_schema(
    operation_id='policy_types_list',
    tags=TAGS,
    summary='List policy types',
    parameters=[PolicyTypeListQuerySerializer, *PAGINATION_PARAMETERS],
    responses={200: api_response(PolicyTypeSerializer, paginated=True), **error_responses(400, 401, 403)},
)


policy_type_create = extend_schema(
    operation_id='policy_types_create',
    tags=TAGS,
    summary='Create a policy type',
    description='Records an "added" note listing every field.',
    request=PolicyTypeCreateSerializer,
    responses={201: api_response(PolicyTypeSerializer), **error_responses(400, 401, 403)},
)


policy_type_detail = combine_schemas(
    extend_schema(
        methods=['GET'],
        tags=TAGS,
        summary='Get a policy type',
        responses={200: api_response(PolicyTypeSerializer), **error_responses(401, 403, 404)},
    ),
    extend_schema(
        methods=['PATCH'],
        tags=TAGS,
        summary='Update a policy type',
        description='Records an "edited" note when something changed.',
        request=PolicyTypeUpdateSerializer,
        responses={200: api_response(PolicyTypeSerializer), **error_responses(400, 401, 403, 404)},
    ),
    extend_schema(
        methods=['DELETE'],
        tags=TAGS,
        summary='Delete a policy type',
        description='Soft delete: the policy type is hidden and can be restored.',
        responses={200: api_response(), **error_responses(401, 403, 404)},
    ),
)


policy_type_notes = extend_schema(
    operation_id='policy_types_notes',
    tags=TAGS,
    summary="List a policy type's change notes",
    description='Newest first. Not paginated.',
    responses={200: api_response(PolicyTypeNoteSerializer, many=True), **error_responses(401, 403, 404)},
)
