from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
    throttle_scope,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenBlacklistSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.services.user_service import UserService
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
    serializer = LoginSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    return APIResponse(serializer.validated_data, 'Logged in successfully.')


@swagger.refresh
@api_view(['POST'])
@authentication_classes([TokenlessAuthentication])
@permission_classes([AllowAny])
def refresh(request):
    serializer = RefreshSerializer(data=request.data)
    try:
        serializer.is_valid(raise_exception=True)
    except TokenError as exc:
        raise InvalidToken(exc.args[0]) from exc
    return APIResponse(serializer.validated_data, 'Token refreshed successfully.')


@swagger.logout
@api_view(['POST'])
@authentication_classes([TokenlessAuthentication])
@permission_classes([AllowAny])
def logout(request):
    serializer = TokenBlacklistSerializer(data=request.data)
    try:
        serializer.is_valid(raise_exception=True)
    except TokenError as exc:
        raise InvalidToken(exc.args[0]) from exc
    return APIResponse(None, 'Logged out successfully.')


@swagger.me
@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def me(request):
    if request.method == 'GET':
        return APIResponse(UserSerializer(request.user).data, 'Profile fetched successfully.')

    serializer = ProfileUpdateSerializer(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    user = UserService(request.user).update_user(request.user, **serializer.validated_data)
    return APIResponse(UserSerializer(user).data, 'Profile updated successfully.')


@swagger.change_password
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([ScopedRateThrottle])
@throttle_scope('auth')
def change_password(request):
    serializer = ChangePasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = UserService(request.user).change_own_password(
        request.user,
        serializer.validated_data['current_password'],
        serializer.validated_data['new_password'],
    )
    refresh_token = RefreshToken.for_user(user)
    return APIResponse(
        {'access': str(refresh_token.access_token), 'refresh': str(refresh_token)},
        'Password changed successfully.',
    )
