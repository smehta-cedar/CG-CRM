from rest_framework_simplejwt.tokens import RefreshToken

#: Claim carrying User.token_version. Checked on every authenticated request
#: by apps.users.authentication.VersionedJWTAuthentication.
TOKEN_VERSION_CLAIM = 'token_version'


def tokens_for_user(user):
    """Issue an access/refresh pair stamped with the user's token version.

    SimpleJWT copies a refresh token's custom claims onto the access tokens
    minted from it, so refreshing preserves the stamp without any extra work -
    and a bumped version invalidates the whole chain, not just the pair that
    happened to be in hand.
    """
    refresh = RefreshToken.for_user(user)
    refresh[TOKEN_VERSION_CLAIM] = user.token_version
    return {'refresh': str(refresh), 'access': str(refresh.access_token)}
