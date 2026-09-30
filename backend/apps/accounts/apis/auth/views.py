from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
    throttle_scope,
)
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.serializers import TokenBlacklistSerializer

from apps.accounts.utils import issue_tokens, send_agent_code, save_user, set_user_password
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
    AgentCodeRequestSerializer,
    AgentLoginSerializer,
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


@swagger.agent_code
@api_view(['POST'])
@authentication_classes([TokenlessAuthentication])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
@throttle_scope('auth')
def agent_code(request):
    # The same reply whether or not a code went out, so the form can't tell.
    serializer = AgentCodeRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    send_agent_code(serializer.validated_data['email'])
    return APIResponse(None, 'If that email has a code, it is on its way.')


@swagger.agent_login
@api_view(['POST'])
@authentication_classes([TokenlessAuthentication])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
@throttle_scope('auth')
def agent_login(request):
    # Work email and the emailed one-time code. No password. validated data is the tokens and the user.
    serializer = AgentLoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return APIResponse(serializer.validated_data, 'Logged in successfully.')


@swagger.agent_home
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agent_home(request):
    """This agent's own record, one section per `agent_view` permission. Staff get a 404.

    A section the role doesn't grant comes back null (and its flag in
    `sections` false). Without "My details" the agent keeps only their name
    and status; without "My licences" their licence rows are left out.
    """
    from apps.agents.apis.agents.serializers import AgentSerializer
    from apps.agents.models import Agent
    from apps.contracts.apis.contracts.serializers import ContractSerializer
    from apps.contracts.models import CarrierContract
    from apps.passwords.apis.passwords.serializers import PasswordSerializer
    from apps.passwords.models import Password
    from apps.policies.apis.certifications.serializers import CertificationSerializer
    from apps.policies.models import Certification

    agent_id = request.user.agent_id
    if not agent_id:
        raise NotFound('No agent profile is linked to this account.')
    agent = Agent.objects.prefetch_related('licenses__state').filter(pk=agent_id).first()
    if agent is None:
        raise NotFound('No agent profile is linked to this account.')
    if not agent.is_active:
        raise PermissionDenied(
            'Your account is blocked. Please contact an administrator.',
            'account_blocked',
        )

    sections = {
        key: request.user.has_permission(f'agent_view.{key}', 'view')
        for key in ('profile', 'licenses', 'contracts', 'certifications', 'passwords')
    }

    agent_data = AgentSerializer(agent).data
    if not sections['profile']:
        kept = ('id', 'name', 'is_active', 'licenses', 'created_at', 'updated_at')
        agent_data = {
            key: value if key in kept else ([] if key == 'aliases' else None if key == 'address' else '')
            for key, value in agent_data.items()
        }
    if not sections['licenses']:
        agent_data['licenses'] = []

    contracts = None
    if sections['contracts']:
        contracts = ContractSerializer(
            CarrierContract.objects.filter(agent=agent)
            .select_related('agent', 'carrier')
            .prefetch_related('appointed_states')
            .order_by('carrier__name'),
            many=True,
        ).data
    certifications = None
    if sections['certifications']:
        certifications = CertificationSerializer(
            Certification.objects.filter(agent=agent)
            .select_related('agent', 'policy_type')
            .prefetch_related('carriers')
            .order_by('policy_type__name'),
            many=True,
        ).data
    passwords = None
    if sections['passwords']:
        passwords = PasswordSerializer(
            Password.objects.filter(agent=agent).select_related('agent', 'carrier').order_by('carrier__name'),
            many=True,
        ).data

    return APIResponse(
        {
            'sections': sections,
            'agent': agent_data,
            'contracts': contracts,
            'certifications': certifications,
            'passwords': passwords,
        },
        'Profile fetched successfully.',
    )


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
