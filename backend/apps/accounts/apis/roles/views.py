from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import Role
from apps.accounts.models.roles import PERMISSION_LABELS
from apps.accounts.utils import (
    filter_roles,
    get_role_or_404,
    normalize_name,
    roles_with_user_count,
    save_role,
    search_roles,
    set_role_permissions,
)
from apps.accounts.validators import ensure_role_name_free, ensure_role_unassigned, ensure_superuser
from apps.base.api.permissions import IsSuperuser, module_permission
from apps.base.api.response import APIResponse

from . import swagger
from .serializers import RoleCreateSerializer, RoleListQuerySerializer, RoleSerializer, RoleUpdateSerializer

# Whoever may see users may see the roles they can be given. Only a superuser
# may add, change or delete a role: a role decides what its users can do, so
# nobody's role should let them widen their own.
CAN_VIEW_USERS = module_permission('users')


@swagger.role_list
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_VIEW_USERS])
def role_list(request):
    # Check the ?search= and ?is_active= values; bad ones give a 400.
    query = RoleListQuerySerializer(data=request.query_params.dict())
    query.is_valid(raise_exception=True)
    filters = query.validated_data

    roles = roles_with_user_count()
    search = filters.get('search')
    if search:
        roles = search_roles(roles, search)
    roles = filter_roles(roles, is_active=filters.get('is_active'))

    # Not paginated: a shop has a handful of roles.
    return APIResponse(RoleSerializer(roles.order_by('name'), many=True).data, 'Roles fetched successfully.')


@swagger.role_modules
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSuperuser])
def role_modules(request):
    modules = [{'code': code, 'label': label} for code, label in PERMISSION_LABELS.items()]
    return APIResponse(modules, 'Modules fetched successfully.')


@swagger.role_create
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsSuperuser])
def role_create(request):
    serializer = RoleCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    name = normalize_name(data['name'])
    ensure_role_name_free(name)

    with transaction.atomic():
        role = Role.objects.create(
            name=name,
            description=data.get('description', ''),
            is_active=data['is_active'],
            created_by=request.user,
            updated_by=request.user,
        )
        set_role_permissions(role, data['permissions'], request.user)
    role = get_role_or_404(role.pk)
    return APIResponse(RoleSerializer(role).data, 'Role created successfully.', status=status.HTTP_201_CREATED)


@swagger.role_detail
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, CAN_VIEW_USERS])
def role_detail(request, pk):
    role = get_role_or_404(pk)

    if request.method == 'GET':
        return APIResponse(RoleSerializer(role).data, 'Role fetched successfully.')

    # PATCH and DELETE change the role, so only a superuser gets past here.
    ensure_superuser(request.user)

    if request.method == 'PATCH':
        # partial=True: only the fields that were sent get updated.
        serializer = RoleUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields = dict(serializer.validated_data)
        permissions = fields.pop('permissions', None)

        if 'name' in fields:
            fields['name'] = normalize_name(fields['name'])
            ensure_role_name_free(fields['name'], exclude=role)

        with transaction.atomic():
            if fields:
                save_role(role, request.user, **fields)
            if permissions is not None:
                set_role_permissions(role, permissions, request.user)
        role = get_role_or_404(role.pk)
        return APIResponse(RoleSerializer(role).data, 'Role updated successfully.')

    # DELETE: soft delete, once no live user holds the role.
    ensure_role_unassigned(role)
    role.delete(user=request.user)
    return APIResponse(None, 'Role deleted successfully.')
