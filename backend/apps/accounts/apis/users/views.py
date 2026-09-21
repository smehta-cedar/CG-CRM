from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import User
from apps.accounts.utils import (
    filter_users,
    get_user_or_404,
    normalize_email,
    revoke_tokens,
    save_user,
    search_users,
    set_user_password,
)
from apps.accounts.validators import (
    ensure_can_manage,
    ensure_email_free,
    ensure_not_self,
    ensure_own_role_unchanged,
    ensure_password_strong,
)
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

# The rules (apps.accounts.validators) enforced in the views below:
#   - only a superuser can change a superuser account
#   - nobody can block or delete their own account, or change their own role
# Blocking, deleting and password changes also sign the user out everywhere.


@swagger.user_list
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_USERS])
def user_list(request):
    # Check the ?search=, ?role_id=, ?designation_id= and ?is_active= values; bad ones give a 400.
    query = UserListQuerySerializer(data=request.query_params.dict())
    query.is_valid(raise_exception=True)
    filters = query.validated_data

    # All users, with each one's role and designation loaded in the same query.
    users = User.objects.select_related('role', 'designation')

    search = filters.get('search')
    if search:
        users = search_users(users, search)

    users = filter_users(
        users,
        role_id=filters.get('role_id'),
        designation_id=filters.get('designation_id'),
        is_active=filters.get('is_active'),
    )

    # Cut the requested page (?page=, ?page_size=); meta holds the page numbers and totals.
    page, meta = paginate(request, users)
    serializer = UserSerializer(page, many=True)
    return APIResponse(serializer.data, 'Users fetched successfully.', meta=meta)


@swagger.user_create
@api_view(['POST'])
@permission_classes([IsAuthenticated, CAN_MANAGE_USERS])
def user_create(request):
    serializer = UserCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    email = normalize_email(data['email'])
    ensure_email_free(email)
    # The unsaved User lets the check reject passwords too similar to the email or name.
    ensure_password_strong(data['password'], User(email=email, full_name=data['full_name']), field='password')

    user = User.objects.create_user(
        email=email,
        password=data['password'],
        full_name=data['full_name'],
        phone=data.get('phone', ''),
        role=data.get('role'),
        designation=data.get('designation'),
        created_by=request.user,
        updated_by=request.user,
    )
    return APIResponse(UserSerializer(user).data, 'User created successfully.', status=status.HTTP_201_CREATED)


@swagger.user_detail
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, CAN_MANAGE_USERS])
def user_detail(request, pk):
    user = get_user_or_404(pk)

    if request.method == 'GET':
        return APIResponse(UserSerializer(user).data, 'User fetched successfully.')

    # PATCH and DELETE change the user, so the permission rules apply from here.
    ensure_can_manage(request.user, user)

    if request.method == 'PATCH':
        # partial=True: only the fields that were sent get updated.
        serializer = UserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields = dict(serializer.validated_data)

        # The email only has to be free when it is actually changing.
        if 'email' in fields:
            fields['email'] = normalize_email(fields['email'])
            if fields['email'] != user.email:
                ensure_email_free(fields['email'])

        if 'role' in fields:
            ensure_own_role_unchanged(request.user, user, fields['role'])

        user = save_user(user, request.user, **fields)
        return APIResponse(UserSerializer(user).data, 'User updated successfully.')

    # DELETE: soft delete the user and sign them out, both or neither.
    ensure_not_self(request.user, user, 'You cannot delete your own account.')
    with transaction.atomic():
        user.delete(user=request.user)
        revoke_tokens(user)
    return APIResponse(None, 'User deleted successfully.')


@swagger.user_block
@api_view(['POST'])
@permission_classes([IsAuthenticated, CAN_UPDATE_USERS])
def user_block(request, pk):
    user = get_user_or_404(pk)
    ensure_can_manage(request.user, user)
    ensure_not_self(request.user, user, 'You cannot block your own account.')
    # Blocking an already blocked user changes nothing and still succeeds.
    if user.is_active:
        with transaction.atomic():
            save_user(user, request.user, is_active=False)
            revoke_tokens(user)
    return APIResponse(UserSerializer(user).data, 'User blocked successfully.')


@swagger.user_unblock
@api_view(['POST'])
@permission_classes([IsAuthenticated, CAN_UPDATE_USERS])
def user_unblock(request, pk):
    user = get_user_or_404(pk)
    ensure_can_manage(request.user, user)
    if not user.is_active:
        save_user(user, request.user, is_active=True)
    return APIResponse(UserSerializer(user).data, 'User unblocked successfully.')


@swagger.user_set_password
@api_view(['POST'])
@permission_classes([IsAuthenticated, CAN_UPDATE_USERS])
def user_set_password(request, pk):
    user = get_user_or_404(pk)
    ensure_can_manage(request.user, user)
    serializer = SetPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    new_password = serializer.validated_data['new_password']

    ensure_password_strong(new_password, user, field='new_password')
    set_user_password(user, request.user, new_password)
    return APIResponse(None, 'Password updated successfully.')
