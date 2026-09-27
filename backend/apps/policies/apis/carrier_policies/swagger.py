"""Swagger docs for the carrier policy endpoints, one per view in views.py."""
from drf_spectacular.utils import extend_schema

from apps.base.api.schema import (
    PAGINATION_PARAMETERS,
    api_response,
    combine_schemas,
    error_responses,
)

from .serializers import (
    CarrierPolicyCreateSerializer,
    CarrierPolicyListQuerySerializer,
    CarrierPolicyNoteSerializer,
    CarrierPolicySerializer,
    CarrierPolicyUpdateSerializer,
)

TAGS = ['Carrier policies']


carrier_policy_list = extend_schema(
    operation_id='carrier_policies_list',
    tags=TAGS,
    summary='List carrier policies',
    description='Sorted by name. Needs the carriers permission.',
    parameters=[CarrierPolicyListQuerySerializer, *PAGINATION_PARAMETERS],
    responses={200: api_response(CarrierPolicySerializer, paginated=True), **error_responses(400, 401, 403)},
)


carrier_policy_create = extend_schema(
    operation_id='carrier_policies_create',
    tags=TAGS,
    summary='Create a carrier policy',
    description=(
        'The name must be free among the carrier\'s live policies (ignoring case) and every '
        'state must be on the carrier\'s available states. Records an "added" note listing every field.'
    ),
    request=CarrierPolicyCreateSerializer,
    responses={201: api_response(CarrierPolicySerializer), **error_responses(400, 401, 403)},
)


carrier_policy_detail = combine_schemas(
    extend_schema(
        methods=['GET'],
        tags=TAGS,
        summary='Get a carrier policy',
        responses={200: api_response(CarrierPolicySerializer), **error_responses(401, 403, 404)},
    ),
    extend_schema(
        methods=['PATCH'],
        tags=TAGS,
        summary='Update a carrier policy',
        description='Records an "edited" note when something changed. The carrier itself cannot change.',
        request=CarrierPolicyUpdateSerializer,
        responses={200: api_response(CarrierPolicySerializer), **error_responses(400, 401, 403, 404)},
    ),
    extend_schema(
        methods=['DELETE'],
        tags=TAGS,
        summary='Delete a carrier policy',
        description='Soft delete: the policy is hidden and its name is free for the carrier to reuse.',
        responses={200: api_response(), **error_responses(401, 403, 404)},
    ),
)


carrier_policy_notes = extend_schema(
    operation_id='carrier_policies_notes',
    tags=TAGS,
    summary="List a carrier policy's change notes",
    description='Newest first. Not paginated.',
    responses={200: api_response(CarrierPolicyNoteSerializer, many=True), **error_responses(401, 403, 404)},
)
