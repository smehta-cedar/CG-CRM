from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.accounts.selectors.user_selector import UserSelector
from apps.accounts.services.user_service import UserService
from apps.base.api.pagination import paginate
from apps.base.api.permissions import module_permission
from apps.base.api.response import APIResponse

from . import swagger
from .serializers import (
    SetPasswordSerializer,
    UserCreateSerializer,
    UserListQuerySerializer,
    UserSerializer,
    UserUpdateSerializer,
)

CAN_MANAGE_USERS = module_permission('users')
# Block, unblock and set-password are POSTs that change a user.
CAN_UPDATE_USERS = module_permission('users', {'POST': 'update'})


@swagger.user_list_create
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, CAN_MANAGE_USERS])
def user_list_create(request):
    if request.method == 'GET':
        query = UserListQuerySerializer(data=request.query_params.dict())
        query.is_valid(raise_exception=True)
        params = query.validated_data

        users = (
            UserSelector(request)
            .search(params.get('search'))
            .filter_role(params.get('role_id'))
            .filter_designation(params.get('designation_id'))
            .filter_active(params.get('is_active'))
            .get_queryset()
        )
        return paginate(request, users, UserSerializer, 'Users fetched successfully.')

    serializer = UserCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = UserService(request.user).create_user(**serializer.validated_data)
    return APIResponse(UserSerializer(user).data, 'User created successfully.', status=status.HTTP_201_CREATED)


@swagger.user_detail
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, CAN_MANAGE_USERS])
def user_detail(request, pk):
    user = UserSelector(request).get_object_or_404(pk=pk)

    if request.method == 'GET':
        return APIResponse(UserSerializer(user).data, 'User fetched successfully.')

    if request.method == 'PATCH':
        serializer = UserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = UserService(request.user).update_user(user, **serializer.validated_data)
        return APIResponse(UserSerializer(user).data, 'User updated successfully.')

    UserService(request.user).delete_user(user)
    return APIResponse(None, 'User deleted successfully.')


@swagger.user_block
@api_view(['POST'])
@permission_classes([IsAuthenticated, CAN_UPDATE_USERS])
def user_block(request, pk):
    user = UserSelector(request).get_object_or_404(pk=pk)
    user = UserService(request.user).block_user(user)
    return APIResponse(UserSerializer(user).data, 'User blocked successfully.')


@swagger.user_unblock
@api_view(['POST'])
@permission_classes([IsAuthenticated, CAN_UPDATE_USERS])
def user_unblock(request, pk):
    user = UserSelector(request).get_object_or_404(pk=pk)
    user = UserService(request.user).unblock_user(user)
    return APIResponse(UserSerializer(user).data, 'User unblocked successfully.')


@swagger.user_set_password
@api_view(['POST'])
@permission_classes([IsAuthenticated, CAN_UPDATE_USERS])
def user_set_password(request, pk):
    user = UserSelector(request).get_object_or_404(pk=pk)
    serializer = SetPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    UserService(request.user).set_password(user, serializer.validated_data['new_password'])
    return APIResponse(None, 'Password updated successfully.')
