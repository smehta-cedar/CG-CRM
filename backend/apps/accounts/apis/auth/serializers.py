from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer

from ..users.serializers import SetPasswordSerializer, UserSerializer


class LoginSerializer(TokenObtainPairSerializer):
    """Email and password in; a token pair and the user out."""

    def validate(self, attrs):
        tokens = super().validate(attrs)
        return {**tokens, 'user': UserSerializer(self.user).data}


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
