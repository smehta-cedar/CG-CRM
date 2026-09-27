from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User, UserNote

# Helpers the account views share. Checks that can reject a request live in
# apps.accounts.validators instead.


def get_user_or_404(pk):
    return get_object_or_404(User.objects.select_related('role', 'designation'), pk=pk)


def search_users(users, search):
    """Narrow `users` to those whose email, name, phone, role or designation matches."""
    return users.filter(
        Q(email__icontains=search)
        | Q(full_name__icontains=search)
        | Q(phone__icontains=search)
        | Q(role__name__icontains=search)
        | Q(designation__name__icontains=search)
    )


def filter_users(users, role_id=None, designation_id=None, is_active=None):
    """Narrow `users` by role, designation and active status; None means no filter."""
    if role_id:
        users = users.filter(role_id=role_id)
    if designation_id:
        users = users.filter(designation_id=designation_id)
    if is_active is not None:
        users = users.filter(is_active=is_active)
    return users


def normalize_email(email):
    # Emails are stored lowercase (see User.save).
    return email.strip().lower()


def save_user(user, actor, **fields):
    """Set `fields` on the user and record `actor` as updated_by."""
    for name, value in fields.items():
        setattr(user, name, value)
    user.updated_by = actor
    user.save(update_fields=[*fields, 'updated_by'])
    return user


def set_user_password(user, actor, new_password):
    """Store the new password and sign the user out everywhere, both or neither."""
    # set_password only hashes the password on the user; save_user stores the hash.
    user.set_password(new_password)
    with transaction.atomic():
        save_user(user, actor, password=user.password)
        revoke_tokens(user)


def revoke_tokens(user):
    """Blacklist every refresh token issued to the user.

    Access tokens need no work: SimpleJWT already rejects them once the
    user is inactive, deleted, or has a new password (CHECK_REVOKE_TOKEN).
    """
    tokens = OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True)
    BlacklistedToken.objects.bulk_create(
        [BlacklistedToken(token=token) for token in tokens],
        ignore_conflicts=True,
    )


# The order a user note lists changed fields in. "password" is recorded redacted.
NOTE_FIELDS = ('name', 'email', 'phone', 'role', 'status', 'password')
REDACTED_FIELDS = ('password',)


def snapshot(user):
    """The user's fields as a note shows them: the role by name, the status as
    active / inactive. The password hash is compared but never written."""
    return {
        'name': user.full_name,
        'email': user.email,
        'phone': user.phone,
        'role': user.role.name if user.role else '',
        'status': 'active' if user.is_active else 'inactive',
        'password': user.password,
    }


def diff_snapshots(before, after):
    """Fields whose value differs, in NOTE_FIELDS order; redacted fields say
    only that they changed. `before` is {} for a new user."""
    changes = []
    for field in NOTE_FIELDS:
        from_value = before.get(field, '')
        to_value = after.get(field, '')
        if from_value == to_value:
            continue
        if field in REDACTED_FIELDS:
            changes.append({'field': field, 'from': '', 'to': '', 'redacted': True})
        else:
            changes.append({'field': field, 'from': from_value, 'to': to_value})
    return changes


def record_note(user, actor, kind, changes):
    """Append a change note. Nothing is written when there are no changes."""
    if not changes:
        return None
    return UserNote.objects.create(user=user, kind=kind, changes=changes, created_by=actor, updated_by=actor)


def issue_tokens(user):
    refresh_token = RefreshToken.for_user(user)
    return {'access': str(refresh_token.access_token), 'refresh': str(refresh_token)}
