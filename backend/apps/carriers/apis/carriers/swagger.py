"""Swagger docs for the carriers endpoints, one per view in views.py."""
from drf_spectacular.utils import extend_schema

from apps.base.api.schema import (
    PAGINATION_PARAMETERS,
    api_response,
    combine_schemas,
    error_responses,
)

from .serializers import (
    CarrierCreateSerializer,
    CarrierListQuerySerializer,
    CarrierNoteSerializer,
    CarrierSerializer,
    CarrierUpdateSerializer,
)

TAGS = ['Carriers']


carrier_list = extend_schema(
    operation_id='carriers_list',
    tags=TAGS,
    summary='List carriers',
    parameters=[CarrierListQuerySerializer, *PAGINATION_PARAMETERS],
    responses={200: api_response(CarrierSerializer, paginated=True), **error_responses(400, 401, 403)},
)


carrier_create = extend_schema(
    operation_id='carriers_create',
    tags=TAGS,
    summary='Create a carrier',
    description='Records an "added" note listing every filled field.',
    request=CarrierCreateSerializer,
    responses={201: api_response(CarrierSerializer), **error_responses(400, 401, 403)},
)


carrier_detail = combine_schemas(
    extend_schema(
        methods=['GET'],
        tags=TAGS,
        summary='Get a carrier',
        responses={200: api_response(CarrierSerializer), **error_responses(401, 403, 404)},
    ),
    extend_schema(
        methods=['PATCH'],
        tags=TAGS,
        summary='Update a carrier',
        description='Records an "edited" note when something changed.',
        request=CarrierUpdateSerializer,
        responses={200: api_response(CarrierSerializer), **error_responses(400, 401, 403, 404)},
    ),
    extend_schema(
        methods=['DELETE'],
        tags=TAGS,
        summary='Delete a carrier',
        description='Soft delete: the carrier is hidden and can be restored.',
        responses={200: api_response(), **error_responses(401, 403, 404)},
    ),
)


carrier_notes = extend_schema(
    operation_id='carriers_notes',
    tags=TAGS,
    summary="List a carrier's change notes",
    description='Newest first. Not paginated.',
    responses={200: api_response(CarrierNoteSerializer, many=True), **error_responses(401, 403, 404)},
)
