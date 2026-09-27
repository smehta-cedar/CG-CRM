"""Swagger docs for the agency contract endpoints, one per view in views.py."""
from drf_spectacular.utils import extend_schema

from apps.base.api.schema import (
    PAGINATION_PARAMETERS,
    api_response,
    combine_schemas,
    error_responses,
)

from .serializers import (
    AgencyContractCreateSerializer,
    AgencyContractListQuerySerializer,
    AgencyContractNoteSerializer,
    AgencyContractSerializer,
    AgencyContractUpdateSerializer,
)

TAGS = ['Agency contracts']


agency_contract_list = extend_schema(
    operation_id='agency_contracts_list',
    tags=TAGS,
    summary='List agency contracts',
    description='Sorted by carrier name.',
    parameters=[AgencyContractListQuerySerializer, *PAGINATION_PARAMETERS],
    responses={200: api_response(AgencyContractSerializer, paginated=True), **error_responses(400, 401, 403)},
)


agency_contract_create = extend_schema(
    operation_id='agency_contracts_create',
    tags=TAGS,
    summary='Create an agency contract',
    description=(
        'One live contract per carrier; a taken carrier is a 400 under carrier. Every policy must '
        'belong to the carrier. Username and password are both blank or both set. The contract '
        'number may be blank; agents can only be given the carrier once it is set. '
        'Records an "added" note listing every filled field (never the password).'
    ),
    request=AgencyContractCreateSerializer,
    responses={201: api_response(AgencyContractSerializer), **error_responses(400, 401, 403)},
)


agency_contract_detail = combine_schemas(
    extend_schema(
        methods=['GET'],
        tags=TAGS,
        summary='Get an agency contract',
        responses={200: api_response(AgencyContractSerializer), **error_responses(401, 403, 404)},
    ),
    extend_schema(
        methods=['PATCH'],
        tags=TAGS,
        summary='Update an agency contract',
        description='Records an "edited" note when something changed (never the password).',
        request=AgencyContractUpdateSerializer,
        responses={200: api_response(AgencyContractSerializer), **error_responses(400, 401, 403, 404)},
    ),
    extend_schema(
        methods=['DELETE'],
        tags=TAGS,
        summary='Delete an agency contract',
        description='Soft delete: the contract is hidden and the carrier can be contracted again.',
        responses={200: api_response(), **error_responses(401, 403, 404)},
    ),
)


agency_contract_notes = extend_schema(
    operation_id='agency_contracts_notes',
    tags=TAGS,
    summary="List an agency contract's change notes",
    description='Newest first. Not paginated.',
    responses={200: api_response(AgencyContractNoteSerializer, many=True), **error_responses(401, 403, 404)},
)
