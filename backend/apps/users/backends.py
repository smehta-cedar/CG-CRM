from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """ModelBackend that also honours `is_blocked`.

    Django's default only consults `is_active`, so without this a blocked user
    would keep signing in - including through the JWT token endpoint, which
    calls `authenticate()` like everything else.
    """

    def user_can_authenticate(self, user):
        return super().user_can_authenticate(user) and not getattr(
            user, 'is_blocked', False
        )
