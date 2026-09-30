from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer

from apps.accounts.utils import normalize_email

from ..users.serializers import SetPasswordSerializer, UserSerializer


class LoginSerializer(TokenObtainPairSerializer):
    """Email and password in; a token pair and the user out.

    How a failed login is answered, so the frontend can tell them apart:

        400 invalid              a field is missing, blank or not an email (see "errors")
        401 invalid_credentials  unknown email or wrong password
        403 account_blocked      right password, but the account is blocked
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # SimpleJWT takes any text here; an EmailField rejects a malformed email as a field error.
        self.fields['email'] = serializers.EmailField(write_only=True)

    def validate(self, attrs):
        try:
            tokens = super().validate(attrs)
        except AuthenticationFailed as exc:
            # SimpleJWT answers every failure the same way; say which one it was.
            if self._is_blocked_user(attrs['email'], attrs['password']):
                raise PermissionDenied(
                    'Your account is blocked. Please contact an administrator.', 'account_blocked'
                ) from exc
            raise AuthenticationFailed('Incorrect email or password.', 'invalid_credentials') from exc
        return {**tokens, 'user': UserSerializer(self.user).data}

    @staticmethod
    def _is_blocked_user(email, password):
        # Only someone who knows the password is told that the account is blocked.
        user = get_user_model().objects.filter(email=normalize_email(email), is_active=False).first()
        return user is not None and user.check_password(password)


class AgentCodeRequestSerializer(serializers.Serializer):
    """The work email to send a one-time sign-in code to."""

    email = serializers.EmailField(write_only=True)


class AgentLoginSerializer(serializers.Serializer):
    """Work email and the one-time code emailed to it in; a token pair and the user out.

    There is no password. A wrong email or code is the same answer, so the
    form cannot tell which one failed.

        400 invalid              a field is missing or the email is not an email
        401 invalid_credentials  unknown email, or a wrong, used or expired code
        403 account_blocked      right code, but the agent is inactive
        403 staff_account        the email belongs to a staff account
    """

    email = serializers.EmailField(write_only=True)
    code = serializers.CharField(write_only=True, trim_whitespace=True, allow_blank=False)

    def validate(self, attrs):
        from django.contrib.auth.models import update_last_login

        from apps.accounts.utils import agent_for_email, issue_tokens, user_for_agent, verify_agent_code

        agent = agent_for_email(attrs['email'])
        if agent is None or not verify_agent_code(agent, attrs['code']):
            raise AuthenticationFailed('Incorrect email or code.', 'invalid_credentials')
        if not agent.is_active:
            raise PermissionDenied(
                'Your account is blocked. Please contact an administrator.',
                'account_blocked',
            )

        user = user_for_agent(agent)
        if not user.is_active:
            raise PermissionDenied(
                'Your account is blocked. Please contact an administrator.',
                'account_blocked',
            )
        update_last_login(None, user)
        tokens = issue_tokens(user)
        return {**tokens, 'user': UserSerializer(user).data}


class RefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except get_user_model().DoesNotExist as exc:
            # SimpleJWT looks the user up without a guard, so a token for a
            # soft-deleted user would otherwise be a 500.
            raise AuthenticationFailed(
                self.error_messages['no_active_account'], 'no_active_account'
            ) from exc


class TokensSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class TokenPairWithUserSerializer(TokensSerializer):
    """Docs only: what the login endpoint returns."""

    user = UserSerializer()


class ProfileUpdateSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255, required=False)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)


class ChangePasswordSerializer(SetPasswordSerializer):
    current_password = serializers.CharField(
        write_only=True, trim_whitespace=False, style={'input_type': 'password'}
    )
