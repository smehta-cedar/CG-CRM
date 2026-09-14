from rest_framework_simplejwt.authentication import JWTAuthentication


class TokenlessAuthentication(JWTAuthentication):
    """For public endpoints such as login and refresh.

    Ignores the Authorization header, so a stale access token cannot block
    the request. It is still an authenticator, so DRF keeps credential and
    token failures as 401; with no authenticator at all it turns them into 403.
    """

    def authenticate(self, request):
        return None
