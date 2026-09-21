"""Swagger docs for the users endpoints, one per view in views.py."""
from drf_spectacular.utils import extend_schema

from apps.base.api.schema import (
    PAGINATION_PARAMETERS,
    api_response,
    combine_schemas,
    error_responses,
)

from .serializers import (
    SetPasswordSerializer,
    UserCreateSerializer,
    UserListQuerySerializer,
    UserSerializer,
    UserUpdateSerializer,
)

TAGS = ['Users']


user_list = extend_schema(
    operation_id='users_list',
    tags=TAGS,
    summary='List users',
    parameters=[UserListQuerySerializer, *PAGINATION_PARAMETERS],
    responses={200: api_response(UserSerializer, paginated=True), **error_responses(400, 401, 403)},
)


user_create = extend_schema(
    operation_id='users_create',
    tags=TAGS,
    summary='Create a user',
    request=UserCreateSerializer,
    responses={201: api_response(UserSerializer), **error_responses(400, 401, 403)},
)


user_detail = combine_schemas(
    extend_schema(
        methods=['GET'],
        tags=TAGS,
        summary='Get a user',
        responses={200: api_response(UserSerializer), **error_responses(401, 403, 404)},
    ),
    extend_schema(
        methods=['PATCH'],
        tags=TAGS,
        summary='Update a user',
        request=UserUpdateSerializer,
        responses={200: api_response(UserSerializer), **error_responses(400, 401, 403, 404)},
    ),
    extend_schema(
        methods=['DELETE'],
        tags=TAGS,
        summary='Delete a user',
        description='Soft delete: the account is hidden and signed out, and can be restored.',
        responses={200: api_response(), **error_responses(401, 403, 404)},
    ),
)


user_block = extend_schema(
    tags=TAGS,
    summary='Block a user',
    description='The user can no longer log in and is signed out everywhere.',
    request=None,
    responses={200: api_response(UserSerializer), **error_responses(401, 403, 404)},
)


user_unblock = extend_schema(
    tags=TAGS,
    summary='Unblock a user',
    request=None,
    responses={200: api_response(UserSerializer), **error_responses(401, 403, 404)},
)


user_set_password = extend_schema(
    tags=TAGS,
    summary="Set a user's password",
    description='The user is signed out everywhere and must log in with the new password.',
    request=SetPasswordSerializer,
    responses={200: api_response(), **error_responses(400, 401, 403, 404)},
)
