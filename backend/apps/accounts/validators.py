from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from apps.accounts.models import User

# Every check the account views run. Each one returns nothing when the check
# passes and raises when it fails:
#   ValidationError   -> 400, field errors under "errors"
#   PermissionDenied  -> 403
#   InvalidToken      -> 401


def ensure_can_manage(actor, user):
    if user.is_superuser and not actor.is_superuser:
        raise PermissionDenied('Only a superuser can change a superuser account.')


def ensure_not_self(actor, user, message):
    if actor.pk == user.pk:
        raise PermissionDenied(message)


def ensure_own_role_unchanged(actor, user, new_role):
    """Nobody but a superuser can change their own role."""
    if actor.pk != user.pk or actor.is_superuser:
        return
    new_role_id = new_role.pk if new_role else None
    if new_role_id != user.role_id:
        raise PermissionDenied('You cannot change your own role.')


def ensure_email_free(email):
    # all_objects: a soft-deleted user still holds their email.
    if User.all_objects.filter(email=email).exists():
        raise ValidationError({'email': ['A user with this email already exists.']})


def ensure_password_strong(password, user, field):
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        raise ValidationError({field: exc.messages}) from exc


def ensure_token_valid(serializer):
    """Run a SimpleJWT serializer; a bad or expired refresh token gives a 401, not a 500."""
    try:
        serializer.is_valid(raise_exception=True)
    except TokenError as exc:
        raise InvalidToken(exc.args[0]) from exc


def ensure_current_password(user, current_password):
    if not user.check_password(current_password):
        raise ValidationError({'current_password': ['Current password is incorrect.']})


def ensure_password_changed(current_password, new_password):
    if current_password == new_password:
        raise ValidationError({'new_password': ['New password must be different from the current one.']})
