"""Swagger docs for the contracts endpoints, one per view in views.py."""
from drf_spectacular.utils import extend_schema

from apps.base.api.schema import (
    PAGINATION_PARAMETERS,
    api_response,
    combine_schemas,
    error_responses,
)

from .serializers import (
    ContractCreateSerializer,
    ContractListQuerySerializer,
    ContractNoteSerializer,
    ContractSerializer,
    ContractUpdateSerializer,
)

TAGS = ['Contracts']


contract_list = extend_schema(
    operation_id='contracts_list',
    tags=TAGS,
    summary='List contracts',
    description='Appointments, by agent name then carrier name.',
    parameters=[ContractListQuerySerializer, *PAGINATION_PARAMETERS],
    responses={200: api_response(ContractSerializer, paginated=True), **error_responses(400, 401, 403)},
)


contract_create = extend_schema(
    operation_id='contracts_create',
    tags=TAGS,
    summary='Create a contract',
    description=(
        'One per agent at each carrier. Appointed states must be ones the carrier is available '
        'in and the agent is licensed in. Records an "added" note.'
    ),
    request=ContractCreateSerializer,
    responses={201: api_response(ContractSerializer), **error_responses(400, 401, 403)},
)


contract_detail = combine_schemas(
    extend_schema(
        methods=['GET'],
        tags=TAGS,
        summary='Get a contract',
        responses={200: api_response(ContractSerializer), **error_responses(401, 403, 404)},
    ),
    extend_schema(
        methods=['PATCH'],
        tags=TAGS,
        summary='Update a contract',
        description='Records an "edited" note when something changed.',
        request=ContractUpdateSerializer,
        responses={200: api_response(ContractSerializer), **error_responses(400, 401, 403, 404)},
    ),
    extend_schema(
        methods=['DELETE'],
        tags=TAGS,
        summary='Delete a contract',
        description='Soft delete: the contract is hidden and can be restored.',
        responses={200: api_response(), **error_responses(401, 403, 404)},
    ),
)


contract_notes = extend_schema(
    operation_id='contracts_notes',
    tags=TAGS,
    summary="List a contract's change notes",
    description='Newest first. Not paginated.',
    responses={200: api_response(ContractNoteSerializer, many=True), **error_responses(401, 403, 404)},
)


contract_notes_all = extend_schema(
    operation_id='contracts_notes_all',
    tags=TAGS,
    summary="List every contract's change notes",
    description='Newest first, paginated.',
    parameters=PAGINATION_PARAMETERS,
    responses={200: api_response(ContractNoteSerializer, paginated=True), **error_responses(401, 403)},
)
