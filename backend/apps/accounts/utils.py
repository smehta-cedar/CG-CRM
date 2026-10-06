from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Role, RolePermission, User, UserNote
from apps.accounts.models.roles import ACTIONS, PERMISSION_LABELS

# Helpers the account views share. Checks that can reject a request live in
# apps.accounts.validators instead.


def get_user_or_404(pk):
    return get_object_or_404(User.objects.select_related('designation').prefetch_related('roles'), pk=pk)


def search_users(users, search):
    """Narrow `users` to those whose email, name, phone, any role or designation matches."""
    # distinct: a user with two matching roles would otherwise come back twice.
    return users.filter(
        Q(email__icontains=search)
        | Q(full_name__icontains=search)
        | Q(phone__icontains=search)
        | Q(roles__name__icontains=search)
        | Q(designation__name__icontains=search)
    ).distinct()


def filter_users(users, role_id=None, designation_id=None, is_active=None):
    """Narrow `users` by role (any they hold), designation and active status; None means no filter."""
    if role_id:
        users = users.filter(roles=role_id)
    if designation_id:
        users = users.filter(designation_id=designation_id)
    if is_active is not None:
        users = users.filter(is_active=is_active)
    return users


def normalize_email(email):
    # Emails are stored lowercase (see User.save).
    return email.strip().lower()


def save_user(user, actor, **fields):
    """Set `fields` on the user and record `actor` as updated_by. `roles`, a
    list of Role, replaces the user's roles."""
    roles = fields.pop('roles', None)
    for name, value in fields.items():
        setattr(user, name, value)
    user.updated_by = actor
    user.save(update_fields=[*fields, 'updated_by'])
    if roles is not None:
        user.roles.set(roles)
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
# Notes written before users could hold several roles have "role" instead of "roles".
NOTE_FIELDS = ('name', 'email', 'phone', 'roles', 'status', 'password')
REDACTED_FIELDS = ('password',)


def snapshot(user):
    """The user's fields as a note shows them: the roles by name, the status as
    active / inactive. The password hash is compared but never written."""
    return {
        'name': user.full_name,
        'email': user.email,
        'phone': user.phone,
        'roles': ', '.join(sorted((role.name for role in user.roles.all()), key=str.lower)),
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
    # Copied onto the access token. Staff tokens omit it.
    if user.agent_id:
        refresh_token['agent_id'] = str(user.agent_id)
    return {'access': str(refresh_token.access_token), 'refresh': str(refresh_token)}


def user_for_agent(agent):
    """The sign-in account for this agent, created the first time a code is asked for.

    A staff account that already uses the work email is left alone and refused.
    An account left behind by a deleted agent is reused.
    """
    from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

    from apps.agents.models import Agent

    user = User.objects.filter(agent=agent).first()
    if user is not None:
        return user

    existing = User.objects.filter(email=agent.email).first()
    if existing is not None and existing.agent_id is None:
        raise PermissionDenied(
            'This email is a staff account. Sign in on the staff form.',
            'staff_account',
        )
    if existing is not None and existing.agent_id and existing.agent_id != agent.pk:
        linked = Agent.all_objects.filter(pk=existing.agent_id).first()
        if linked is not None and not linked.is_deleted:
            raise AuthenticationFailed('Incorrect email or code.', 'invalid_credentials')

    if existing is None:
        user = User(email=agent.email, full_name=agent.name, agent=agent)
        user.set_unusable_password()
        user.save()
        return user

    existing.agent = agent
    existing.full_name = agent.name
    existing.is_active = True
    existing.set_unusable_password()
    existing.save()
    return existing


def agent_for_email(email):
    """The one live agent with this work email, or None when there is none or several."""
    from apps.agents.models import Agent

    matches = list(Agent.objects.filter(email=normalize_email(email))[:2])
    return matches[0] if len(matches) == 1 else None


def agent_code_device(user):
    """The email OTP device that sends and checks this sign-in account's codes."""
    from django_otp.plugins.otp_email.models import EmailDevice

    device, _ = EmailDevice.objects.get_or_create(user=user, defaults={'name': 'Agent sign-in'})
    return device


def send_agent_code(email):
    """Email a new one-time sign-in code when `email` is the work email of
    exactly one active agent; otherwise do nothing. The caller answers the
    same either way, so this never says which happened.

    django-otp makes the code (six random digits), keeps it until it is used
    or OTP_EMAIL_TOKEN_VALIDITY runs out, and won't send another within
    OTP_EMAIL_COOLDOWN_DURATION. A new code replaces the last one.
    """
    import logging

    from rest_framework.exceptions import APIException

    agent = agent_for_email(email)
    if agent is None or not agent.is_active:
        return
    try:
        user = user_for_agent(agent)
    except APIException:
        # The email is a staff account, or another agent's sign-in account.
        return
    if not user.is_active:
        return
    try:
        agent_code_device(user).generate_challenge()
    except Exception:
        # The reply can't differ, so a mail failure is only logged.
        logging.getLogger(__name__).exception('Could not email a sign-in code to agent %s.', agent.pk)


def verify_agent_code(agent, code):
    """True when `code` is the agent's current emailed code. A used or expired code never is.
    Wrong guesses slow further checks down (django-otp throttling)."""
    user = User.objects.filter(agent=agent).first()
    if user is None:
        return False
    return agent_code_device(user).verify_token(code)


def sync_agent_login_user(agent):
    """Keep a linked sign-in account on this agent's work email, name and status.

    Does nothing until the agent has asked for a code once. A work email another
    account already uses is rejected.
    """
    from rest_framework.exceptions import ValidationError

    user = User.objects.filter(agent=agent).first()
    if user is None:
        return
    if agent.email and User.objects.filter(email=agent.email).exclude(pk=user.pk).exists():
        raise ValidationError({'email': ['That work email is already used to sign in.']})

    updates = []
    if agent.email and user.email != agent.email:
        user.email = agent.email
        updates.append('email')
    if user.full_name != agent.name:
        user.full_name = agent.name
        updates.append('full_name')
    if user.is_active != agent.is_active:
        user.is_active = agent.is_active
        updates.append('is_active')
    if updates:
        user.save(update_fields=updates)


def deactivate_agent_login(agent):
    """Block the sign-in account when the agent is deleted."""
    user = User.objects.filter(agent=agent).first()
    if user is not None and user.is_active:
        user.is_active = False
        user.save(update_fields=['is_active'])


# Roles. Only superusers change them (see apps.accounts.validators.ensure_superuser).


def roles_with_user_count():
    """Every live role with how many live users hold it, plus its permission rows."""
    return Role.objects.annotate(
        user_count=Count('users', filter=Q(users__deleted_at__isnull=True), distinct=True)
    ).prefetch_related('permissions')


def get_role_or_404(pk):
    return get_object_or_404(roles_with_user_count(), pk=pk)


def search_roles(roles, search):
    """Narrow `roles` to those whose name or description matches."""
    return roles.filter(Q(name__icontains=search) | Q(description__icontains=search))


def filter_roles(roles, is_active=None):
    """Narrow `roles` by active status; None means no filter."""
    if is_active is not None:
        roles = roles.filter(is_active=is_active)
    return roles


def normalize_name(name):
    return ' '.join(name.split())


def save_role(role, actor, **fields):
    """Set `fields` on the role and record `actor` as updated_by."""
    for name, value in fields.items():
        setattr(role, name, value)
    role.updated_by = actor
    role.save(update_fields=[*fields, 'updated_by'])
    return role


def set_role_permissions(role, permissions, actor):
    """Replace the role's permissions: one row per module in the catalog, with
    the flags sent for it or none at all when it was left out."""
    sent = {permission['module']: permission for permission in permissions}
    for module in PERMISSION_LABELS:
        flags = {f'can_{action}': bool(sent.get(module, {}).get(f'can_{action}', False)) for action in ACTIONS}
        RolePermission.objects.update_or_create(
            role=role,
            module=module,
            defaults={**flags, 'updated_by': actor},
            create_defaults={**flags, 'created_by': actor, 'updated_by': actor},
        )
