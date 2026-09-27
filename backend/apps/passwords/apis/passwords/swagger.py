"""Swagger docs for the passwords endpoints, one per view in views.py."""
from drf_spectacular.utils import extend_schema

from apps.base.api.schema import (
    PAGINATION_PARAMETERS,
    api_response,
    combine_schemas,
    error_responses,
)

from .serializers import (
    PasswordCreateSerializer,
    PasswordListQuerySerializer,
    PasswordNoteSerializer,
    PasswordSerializer,
    PasswordUpdateSerializer,
)

TAGS = ['Passwords']


password_list = extend_schema(
    operation_id='passwords_list',
    tags=TAGS,
    summary='List passwords',
    description='Carrier portal logins, by agent name then carrier name.',
    parameters=[PasswordListQuerySerializer, *PAGINATION_PARAMETERS],
    responses={200: api_response(PasswordSerializer, paginated=True), **error_responses(400, 401, 403)},
)


password_create = extend_schema(
    operation_id='passwords_create',
    tags=TAGS,
    summary='Create a password',
    description='One per agent at each carrier. Records an "added" note; the password only as "set".',
    request=PasswordCreateSerializer,
    responses={201: api_response(PasswordSerializer), **error_responses(400, 401, 403)},
)


password_detail = combine_schemas(
    extend_schema(
        methods=['GET'],
        tags=TAGS,
        summary='Get a password',
        responses={200: api_response(PasswordSerializer), **error_responses(401, 403, 404)},
    ),
    extend_schema(
        methods=['PATCH'],
        tags=TAGS,
        summary='Update a password',
        description='Records an "edited" note when something changed; the password only as "changed".',
        request=PasswordUpdateSerializer,
        responses={200: api_response(PasswordSerializer), **error_responses(400, 401, 403, 404)},
    ),
    extend_schema(
        methods=['DELETE'],
        tags=TAGS,
        summary='Delete a password',
        description='Soft delete: the password is hidden and can be restored.',
        responses={200: api_response(), **error_responses(401, 403, 404)},
    ),
)


password_notes = extend_schema(
    operation_id='passwords_notes',
    tags=TAGS,
    summary="List a password's change notes",
    description='Newest first. Not paginated. The password value is never in a note.',
    responses={200: api_response(PasswordNoteSerializer, many=True), **error_responses(401, 403, 404)},
)
