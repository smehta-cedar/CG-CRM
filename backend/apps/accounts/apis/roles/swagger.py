"""Swagger docs for the roles endpoints, one per view in views.py."""
from drf_spectacular.utils import extend_schema

from apps.base.api.schema import api_response, combine_schemas, error_responses

from .serializers import (
    ModuleSerializer,
    RoleCreateSerializer,
    RoleListQuerySerializer,
    RoleSerializer,
    RoleUpdateSerializer,
)

TAGS = ['Roles']


role_list = extend_schema(
    operation_id='roles_list',
    tags=TAGS,
    summary='List roles',
    description='Every live role with its permissions and how many users hold it, by name. Not paginated.',
    parameters=[RoleListQuerySerializer],
    responses={200: api_response(RoleSerializer, many=True), **error_responses(400, 401, 403)},
)


role_modules = extend_schema(
    operation_id='roles_modules',
    tags=TAGS,
    summary='List permission modules',
    description='Every screen a role can be granted, in menu order. Superusers only.',
    responses={200: api_response(ModuleSerializer, many=True), **error_responses(401, 403)},
)


role_create = extend_schema(
    operation_id='roles_create',
    tags=TAGS,
    summary='Create a role',
    description='Superusers only. A module left out of `permissions` gets no access.',
    request=RoleCreateSerializer,
    responses={201: api_response(RoleSerializer), **error_responses(400, 401, 403)},
)


role_detail = combine_schemas(
    extend_schema(
        methods=['GET'],
        tags=TAGS,
        summary='Get a role',
        responses={200: api_response(RoleSerializer), **error_responses(401, 403, 404)},
    ),
    extend_schema(
        methods=['PATCH'],
        tags=TAGS,
        summary='Update a role',
        description='Superusers only. `permissions`, when sent, replaces the whole set.',
        request=RoleUpdateSerializer,
        responses={200: api_response(RoleSerializer), **error_responses(400, 401, 403, 404)},
    ),
    extend_schema(
        methods=['DELETE'],
        tags=TAGS,
        summary='Delete a role',
        description='Superusers only. Soft delete; refused (400) while any user still holds the role.',
        responses={200: api_response(), **error_responses(400, 401, 403, 404)},
    ),
)
