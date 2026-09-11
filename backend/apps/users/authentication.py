from django.utils.translation import gettext_lazy as _
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed

from .tokens import TOKEN_VERSION_CLAIM


class VersionedJWTAuthentication(JWTAuthentication):
    """JWTAuthentication that honours blocking and token invalidation.

    Stock SimpleJWT checks `is_active` and nothing else, so a blocked user
    would keep sailing through on an access token minted before the block.
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)  # checks is_active

        if user.is_blocked:
            raise AuthenticationFailed(
                _('This account has been blocked.'), code='account_blocked'
            )

        # A token predating this mechanism carries no claim, so it reads as
        # None and fails the comparison - it has to be re-issued. That is the
        # safe direction to fail.
        if validated_token.get(TOKEN_VERSION_CLAIM) != user.token_version:
            raise AuthenticationFailed(
                _('This token is no longer valid. Please sign in again.'),
                code='token_not_valid',
            )

        return user


class VersionedJWTScheme(OpenApiAuthenticationExtension):
    """Teaches drf-spectacular to describe the class above.

    Without it every gated view generates a warning and the schema omits its
    security scheme - so "Authorize" in Swagger UI would not appear.
    Registered simply by being imported, which settings does when it resolves
    DEFAULT_AUTHENTICATION_CLASSES.
    """

    target_class = 'apps.users.authentication.VersionedJWTAuthentication'
    name = 'jwtAuth'

    def get_security_definition(self, auto_schema):
        return {'type': 'http', 'scheme': 'bearer', 'bearerFormat': 'JWT'}
