"""Swagger docs for the auth endpoints, one per view in views.py."""
from drf_spectacular.utils import extend_schema
from rest_framework_simplejwt.serializers import TokenBlacklistSerializer

from apps.base.api.schema import api_response, combine_schemas, error_responses

from ..users.serializers import UserSerializer
from .serializers import (
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
    request=LoginSerializer,
    responses={200: api_response(TokenPairWithUserSerializer), **error_responses(400, 401, 429)},
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
        responses={200: api_response(UserSerializer), **error_responses(401)},
    ),
    extend_schema(
        methods=['PATCH'],
        tags=TAGS,
        summary='Update my profile',
        request=ProfileUpdateSerializer,
        responses={200: api_response(UserSerializer), **error_responses(400, 401)},
    ),
)


change_password = extend_schema(
    tags=TAGS,
    summary='Change my password',
    description='Signs out every other session and returns a fresh token pair for this one.',
    request=ChangePasswordSerializer,
    responses={200: api_response(TokensSerializer), **error_responses(400, 401, 429)},
)
