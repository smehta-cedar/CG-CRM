from drf_spectacular.utils import OpenApiExample, extend_schema, inline_serializer
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from apps.roles.permissions import (
    ANY_AUTHENTICATED,
    HasRolePermission,
    require_permission,
)

from .auth_serializers import (
    AdminSetPasswordSerializer,
    ChangeOwnPasswordSerializer,
    LoginSerializer,
)
from .models import User
from .serializers import UserSerializer
from .tokens import tokens_for_user


@extend_schema(tags=['Auth'])
class LoginView(GenericAPIView):
    """Exchange an email and password for a JWT pair.

    Replaces SimpleJWT's stock TokenObtainPairView, which cannot tell the
    three failure modes apart, does not report `must_change_password`, and -
    more importantly - issues tokens with no version stamp, which would leave
    a permanent hole in blocking.
    """

    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        responses={
            200: inline_serializer(
                name='LoginResponse',
                fields={
                    'access': serializers.CharField(),
                    'refresh': serializers.CharField(),
                    'must_change_password': serializers.BooleanField(),
                    'user': UserSerializer(),
                },
            ),
        },
        examples=[
            OpenApiExample(
                'Blocked account',
                value={
                    'detail': 'This account has been blocked. Contact an administrator.',
                    'code': 'account_blocked',
                },
                response_only=True,
                status_codes=['401'],
            ),
        ],
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        return Response({
            **tokens_for_user(user),
            'must_change_password': user.must_change_password,
            # Saves the frontend an immediate round trip to /users/me/ for the
            # permission codenames it needs to draw the menu.
            'user': UserSerializer(user, context=self.get_serializer_context()).data,
        })


@extend_schema(tags=['Auth'])
class ChangeOwnPasswordView(GenericAPIView):
    """Rotate your own password, proving you know the current one."""

    serializer_class = ChangeOwnPasswordSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: inline_serializer(
                name='ChangePasswordResponse',
                fields={
                    'detail': serializers.CharField(),
                    'access': serializers.CharField(),
                    'refresh': serializers.CharField(),
                },
            ),
        },
    )
    # The allow-list that stops the forced-password-change rule deadlocking:
    # this is the endpoint that clears the flag, so it cannot be gated on the
    # flag being clear.
    @require_permission(ANY_AUTHENTICATED, allow_password_change_pending=True)
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response({
            'detail': 'Password changed.',
            # The change invalidated every token including the one used to
            # make this call, so hand back a working pair rather than
            # logging the caller out for doing the right thing.
            **tokens_for_user(user),
        })


@extend_schema(tags=['Users'])
class UserViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """create / update / detail / list for users.

    No destroy: accounts are deactivated (`is_active`) or blocked
    (`is_blocked`) rather than deleted, so records referencing them keep
    making sense.
    """

    queryset = User.objects.select_related('role').order_by('full_name', 'email')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, HasRolePermission]

    required_permissions = {
        'list': 'user.detail',
        'retrieve': 'user.detail',
        'create': 'user.create',
        'update': 'user.update',
        'partial_update': 'user.update',
        'block': 'user.block',
        'unblock': 'user.unblock',
        'change_password': 'user.change_password',
        # Reading yourself is not a privilege - see `me` below.
        'me': ANY_AUTHENTICATED,
    }

    # Reachable while a forced password change is pending. Reading your own
    # profile discloses nothing the login response did not already hand over,
    # and the change-password screen wants a name to greet.
    password_change_exempt_actions = {'me'}

    def get_serializer_class(self):
        if self.action == 'change_password':
            return AdminSetPasswordSerializer
        return super().get_serializer_class()

    def _as_user_response(self, user):
        return Response(
            UserSerializer(user, context=self.get_serializer_context()).data
        )

    @extend_schema(
        responses=UserSerializer,
        description=(
            'The signed-in account, with its role and effective permission '
            'codenames. The frontend renders its menus from this.'
        ),
    )
    # Anyone signed in may read their own account - it is ANY_AUTHENTICATED
    # in the map above. Routing this through `user.detail` would be circular:
    # a low-privilege user needs their permission list to draw a menu, but
    # would need user.detail to fetch it, so they would get no menu at all.
    @action(detail=False, methods=['get'])
    def me(self, request):
        return self._as_user_response(request.user)

    @extend_schema(request=None, responses=UserSerializer)
    @action(detail=True, methods=['post'])
    def block(self, request, pk=None):
        user = self.get_object()

        if user == request.user:
            raise serializers.ValidationError({
                'detail': ['You cannot block your own account.']
            })

        user.is_blocked = True
        user.save(update_fields=['is_blocked'])

        # Two mechanisms, because they cover different tokens. The version
        # bump kills stateless access tokens the moment it lands; blacklisting
        # closes out the refresh tokens on record so they cannot be replayed
        # if the version is ever reset.
        user.invalidate_tokens()
        for outstanding in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=outstanding)

        return self._as_user_response(user)

    @extend_schema(request=None, responses=UserSerializer)
    @action(detail=True, methods=['post'])
    def unblock(self, request, pk=None):
        user = self.get_object()
        user.is_blocked = False
        user.save(update_fields=['is_blocked'])
        # No version bump: their old tokens are already dead from the block,
        # and unblocking is not a reason to invalidate anything further. They
        # sign in again.
        return self._as_user_response(user)

    @extend_schema(
        request=AdminSetPasswordSerializer,
        responses={200: inline_serializer(
            name='AdminSetPasswordResponse',
            fields={'detail': serializers.CharField()},
        )},
    )
    @action(detail=True, methods=['post'], url_path='change-password')
    def change_password(self, request, pk=None):
        user = self.get_object()

        if user == request.user:
            # This endpoint sets must_change_password and drops every session,
            # so aiming it at yourself locks you out of the one you are in.
            raise serializers.ValidationError({
                'detail': ['Use /api/v1/auth/change-password/ to change your own '
                           'password.']
            })

        serializer = self.get_serializer(instance=user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            'detail': (
                f'Password set for {user.email}. They must change it at next '
                f'sign-in, and their existing sessions have ended.'
            ),
        }, status=status.HTTP_200_OK)
