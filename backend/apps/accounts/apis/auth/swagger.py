"""Swagger docs for the auth endpoints, one per view in views.py."""
from drf_spectacular.utils import extend_schema
from rest_framework_simplejwt.serializers import TokenBlacklistSerializer

from apps.base.api.schema import api_response, combine_schemas, error_responses

from ..users.serializers import MeSerializer
from .serializers import (
    AgentCodeRequestSerializer,
    AgentLoginSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    ProfileUpdateSerializer,
    RefreshSerializer,
    TokenPairWithUserSerializer,
    TokensSerializer,
)

TAGS = ['Auth']


# auth=[]: these three are called without an access token.

login = extend_schema(
    tags=TAGS,
    summary='Log in',
    auth=[],
    description=(
        'Error codes: `invalid` (400, a field is missing, blank or not an email), '
        '`invalid_credentials` (401, unknown email or wrong password), '
        '`account_blocked` (403, right password but the account is blocked), '
        '`throttled` (429, too many attempts).'
    ),
    request=LoginSerializer,
    responses={200: api_response(TokenPairWithUserSerializer), **error_responses(400, 401, 403, 429)},
)


agent_code = extend_schema(
    tags=TAGS,
    summary='Email an agent a one-time sign-in code',
    auth=[],
    description=(
        'Emails a new six-digit code to the work email when it belongs to exactly one active agent. '
        'The code works once and expires after five minutes; another is not sent within a minute. '
        'The reply is the same when the email is unknown, shared or inactive. '
        'Error codes: `invalid` (400, not an email), `throttled` (429).'
    ),
    request=AgentCodeRequestSerializer,
    responses={200: api_response(), **error_responses(400, 429)},
)


agent_login = extend_schema(
    tags=TAGS,
    summary='Log in as an agent',
    auth=[],
    description=(
        'Work email and the code from the agent-code email. No password. '
        'Error codes: `invalid` (400), `invalid_credentials` (401, unknown email, or a wrong, used or expired code), '
        '`account_blocked` (403), `staff_account` (403, the email is a staff account), '
        '`throttled` (429).'
    ),
    request=AgentLoginSerializer,
    responses={200: api_response(TokenPairWithUserSerializer), **error_responses(400, 401, 403, 429)},
)


agent_home = extend_schema(
    tags=TAGS,
    summary='Get the signed-in agent profile',
    description=(
        'The agent and, per agent_view permission, their details, licences, appointments, '
        'certifications and portal passwords. A section the role does not grant is null. '
        'A staff account gets 404.'
    ),
    responses={200: api_response(), **error_responses(401, 403, 404)},
)


refresh = extend_schema(
    tags=TAGS,
    summary='Refresh the access token',
    auth=[],
    description='Returns a new token pair; the refresh token sent is no longer valid.',
    request=RefreshSerializer,
    responses={200: api_response(TokensSerializer), **error_responses(400, 401)},
)


logout = extend_schema(
    tags=TAGS,
    summary='Log out',
    auth=[],
    description='Blacklists the refresh token. Drop the access token on the client.',
    request=TokenBlacklistSerializer,
    responses={200: api_response(), **error_responses(400, 401)},
)


me = combine_schemas(
    extend_schema(
        methods=['GET'],
        tags=TAGS,
        summary='Get my profile',
        responses={200: api_response(MeSerializer), **error_responses(401)},
    ),
    extend_schema(
        methods=['PATCH'],
        tags=TAGS,
        summary='Update my profile',
        request=ProfileUpdateSerializer,
        responses={200: api_response(MeSerializer), **error_responses(400, 401)},
    ),
)


change_password = extend_schema(
    tags=TAGS,
    summary='Change my password',
    description='Signs out every other session and returns a fresh token pair for this one.',
    request=ChangePasswordSerializer,
    responses={200: api_response(TokensSerializer), **error_responses(400, 401, 429)},
)
