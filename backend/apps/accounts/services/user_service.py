from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.accounts.models import User
from apps.accounts.selectors.user_selector import UserSelector
from apps.base.services.base import BaseService


class UserService(BaseService):
    """User writes, done on behalf of the acting user:

        UserService(request.user).block_user(user)

    Rules enforced for every caller:
      - only a superuser can change a superuser account
      - nobody can block or delete their own account, or change their own role

    Blocking, deleting and password changes also sign the user out everywhere.
    """

    # What update_user() may change; status and password have their own methods.
    UPDATABLE_FIELDS = frozenset({'email', 'full_name', 'phone', 'role', 'designation'})

    @transaction.atomic
    def create_user(self, *, email, password, full_name, phone='', role=None, designation=None):
        email = email.strip().lower()
        self._ensure_email_free(email)
        self._validate_password(password, User(email=email, full_name=full_name), field='password')
        return User.objects.create_user(
            email=email,
            password=password,
            full_name=full_name,
            phone=phone,
            role=role,
            designation=designation,
            created_by=self.actor,
            updated_by=self.actor,
        )

    @transaction.atomic
    def update_user(self, user, **fields):
        unknown = set(fields) - self.UPDATABLE_FIELDS
        if unknown:
            raise TypeError(f"update_user() cannot change: {', '.join(sorted(unknown))}")

        self._ensure_can_manage(user)

        if 'email' in fields:
            fields['email'] = fields['email'].strip().lower()
            if fields['email'] != user.email:
                self._ensure_email_free(fields['email'])

        if 'role' in fields and self._is_self(user) and not self.actor.is_superuser:
            new_role_id = fields['role'].pk if fields['role'] else None
            if new_role_id != user.role_id:
                raise PermissionDenied('You cannot change your own role.')

        return self._update(user, **fields)

    @transaction.atomic
    def block_user(self, user):
        self._ensure_can_manage(user)
        if self._is_self(user):
            raise PermissionDenied('You cannot block your own account.')
        if user.is_active:
            self._update(user, is_active=False)
            self._revoke_tokens(user)
        return user

    @transaction.atomic
    def unblock_user(self, user):
        self._ensure_can_manage(user)
        if not user.is_active:
            self._update(user, is_active=True)
        return user

    @transaction.atomic
    def set_password(self, user, new_password):
        """An admin setting someone else's password."""
        self._ensure_can_manage(user)
        self._change_password(user, new_password)
        return user

    @transaction.atomic
    def change_own_password(self, user, current_password, new_password):
        if not user.check_password(current_password):
            raise ValidationError({'current_password': 'Current password is incorrect.'})
        if current_password == new_password:
            raise ValidationError({'new_password': 'New password must be different from the current one.'})
        self._change_password(user, new_password)
        return user

    @transaction.atomic
    def delete_user(self, user):
        self._ensure_can_manage(user)
        if self._is_self(user):
            raise PermissionDenied('You cannot delete your own account.')
        self._delete(user)
        self._revoke_tokens(user)

    def _is_self(self, user):
        return self.actor is not None and self.actor.pk == user.pk

    def _ensure_can_manage(self, user):
        if user.is_superuser and self.actor is not None and not self.actor.is_superuser:
            raise PermissionDenied('Only a superuser can change a superuser account.')

    @staticmethod
    def _ensure_email_free(email):
        if UserSelector().email_taken(email):
            raise ValidationError({'email': 'A user with this email already exists.'})

    @staticmethod
    def _validate_password(password, user, field):
        try:
            validate_password(password, user)
        except ValidationError as exc:
            raise ValidationError({field: exc.messages}) from exc

    def _change_password(self, user, new_password):
        self._validate_password(new_password, user, field='new_password')
        user.set_password(new_password)
        self._update(user, password=user.password)
        self._revoke_tokens(user)

    @staticmethod
    def _revoke_tokens(user):
        """Blacklist every refresh token issued to the user.

        Access tokens need no work: SimpleJWT already rejects them once the
        user is inactive, deleted, or has a new password (CHECK_REVOKE_TOKEN).
        """
        tokens = OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True)
        BlacklistedToken.objects.bulk_create(
            [BlacklistedToken(token=token) for token in tokens],
            ignore_conflicts=True,
        )
