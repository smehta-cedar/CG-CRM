"""Serializers for signing in and for changing a password.

Kept apart from serializers.py, which is about representing a user; these are
about acting on one.
"""

from django.contrib.auth import password_validation
from rest_framework import serializers, status
from rest_framework.exceptions import APIException

from .models import User


class LoginFailure(APIException):
    """401 whose body carries a machine-readable `code` beside the message.

    DRF puts an exception's code on the ErrorDetail rather than in the
    response body, and the frontend has to branch on which failure this was.

    Deliberately not an AuthenticationFailed subclass: DRF rewrites those to
    403 unless the view can produce a WWW-Authenticate header, and LoginView
    accepts no credentials at all - so these would all arrive as 403.
    """

    status_code = status.HTTP_401_UNAUTHORIZED

    def __init__(self, detail, code):
        super().__init__({'detail': detail, 'code': code})


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True, style={'input_type': 'password'}, trim_whitespace=False
    )

    def validate(self, attrs):
        email = User.objects.normalize_email(attrs['email'])
        user = User.objects.filter(email__iexact=email).select_related('role').first()

        # Order matters. Until the password has been proven correct, every
        # failure has to look identical, or the endpoint becomes an oracle:
        # anyone could learn which addresses hold accounts, and which of those
        # are blocked, without knowing a single password. Only once the caller
        # has demonstrated they own the account do the specific reasons get
        # disclosed.
        if user is None or not user.check_password(attrs['password']):
            raise LoginFailure(
                'No account matches that email address and password.',
                'invalid_credentials',
            )

        if user.is_blocked:
            raise LoginFailure(
                'This account has been blocked. Contact an administrator.',
                'account_blocked',
            )

        if not user.is_active:
            raise LoginFailure(
                'This account is inactive. Contact an administrator.',
                'account_inactive',
            )

        attrs['user'] = user
        return attrs


class ChangeOwnPasswordSerializer(serializers.Serializer):
    """The signed-in user rotating their own password."""

    old_password = serializers.CharField(
        write_only=True, style={'input_type': 'password'}, trim_whitespace=False
    )
    new_password = serializers.CharField(
        write_only=True, style={'input_type': 'password'}, trim_whitespace=False
    )

    def validate_old_password(self, value):
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError('Your current password is incorrect.')
        return value

    def validate_new_password(self, value):
        # Passing the user lets the similarity and common-password validators
        # actually do their job.
        password_validation.validate_password(value, self.context['request'].user)
        return value

    def validate(self, attrs):
        if attrs['old_password'] == attrs['new_password']:
            raise serializers.ValidationError(
                {'new_password': 'The new password must differ from the current one.'}
            )
        return attrs

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        # Whatever forced the change has now been satisfied.
        user.must_change_password = False
        user.save(update_fields=['password', 'must_change_password'])

        # A password change should end every other session. The caller's own
        # tokens die with them, so the view hands back a fresh pair.
        user.invalidate_tokens()
        return user


class AdminSetPasswordSerializer(serializers.Serializer):
    """An administrator setting someone else's password.

    No old password: the whole point is that the administrator does not know
    it. `must_change_password` is set so the account cannot keep running on a
    password a second person has seen.
    """

    new_password = serializers.CharField(
        write_only=True, style={'input_type': 'password'}, trim_whitespace=False
    )

    def validate_new_password(self, value):
        password_validation.validate_password(value, self.instance)
        return value

    def save(self, **kwargs):
        user = self.instance
        user.set_password(self.validated_data['new_password'])
        user.must_change_password = True
        user.save(update_fields=['password', 'must_change_password'])

        # Their existing sessions are running on the old password.
        user.invalidate_tokens()
        return user
