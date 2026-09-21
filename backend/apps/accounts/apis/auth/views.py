from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
    throttle_scope,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.serializers import TokenBlacklistSerializer

from apps.accounts.utils import issue_tokens, save_user, set_user_password
from apps.accounts.validators import (
    ensure_current_password,
    ensure_password_changed,
    ensure_password_strong,
    ensure_token_valid,
)
from apps.base.api.authentication import TokenlessAuthentication
from apps.base.api.response import APIResponse

from . import swagger
from ..users.serializers import UserSerializer
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    ProfileUpdateSerializer,
    RefreshSerializer,
)

# login, refresh and logout ignore the Authorization header (see
# TokenlessAuthentication), so a stale access token cannot get in the way.
#
# The 'auth' throttle rate lives in settings; it counts per IP when logged
# out and per user when logged in.


@swagger.login
@api_view(['POST'])
@authentication_classes([TokenlessAuthentication])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
@throttle_scope('auth')
def login(request):
    # The serializer checks the email and password; its validated data is the tokens and the user.
    serializer = LoginSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    return APIResponse(serializer.validated_data, 'Logged in successfully.')


@swagger.refresh
@api_view(['POST'])
@authentication_classes([TokenlessAuthentication])
@permission_classes([AllowAny])
def refresh(request):
    serializer = RefreshSerializer(data=request.data)
    ensure_token_valid(serializer)
    return APIResponse(serializer.validated_data, 'Token refreshed successfully.')


@swagger.logout
@api_view(['POST'])
@authentication_classes([TokenlessAuthentication])
@permission_classes([AllowAny])
def logout(request):
    # Validating this serializer is what blacklists the refresh token.
    serializer = TokenBlacklistSerializer(data=request.data)
    ensure_token_valid(serializer)
    return APIResponse(None, 'Logged out successfully.')


@swagger.me
@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def me(request):
    if request.method == 'GET':
        return APIResponse(UserSerializer(request.user).data, 'Profile fetched successfully.')

    # partial=True: only the fields that were sent get updated.
    serializer = ProfileUpdateSerializer(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    # request.user twice: the user being changed, and the one recorded as updated_by.
    user = save_user(request.user, request.user, **serializer.validated_data)
    return APIResponse(UserSerializer(user).data, 'Profile updated successfully.')


@swagger.change_password
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([ScopedRateThrottle])
@throttle_scope('auth')
def change_password(request):
    serializer = ChangePasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    current_password = serializer.validated_data['current_password']
    new_password = serializer.validated_data['new_password']

    user = request.user
    ensure_current_password(user, current_password)
    ensure_password_changed(current_password, new_password)
    ensure_password_strong(new_password, user, field='new_password')

    set_user_password(user, user, new_password)

    # The old tokens were just revoked, so send new ones to keep this session logged in.
    return APIResponse(issue_tokens(user), 'Password changed successfully.')
