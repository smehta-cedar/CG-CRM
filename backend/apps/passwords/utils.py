from django.db.models import Q
from django.shortcuts import get_object_or_404

from apps.passwords.models import Password, PasswordNote

# Helpers the password views share. Checks that can reject a request live in
# apps.passwords.validators instead.

# The order a note lists changed fields in. "password" is recorded redacted.
NOTE_FIELDS = ('agent', 'carrier', 'username', 'password', 'link', 'status')
REDACTED_FIELDS = ('password',)


def get_password_or_404(pk):
    return get_object_or_404(Password.objects.select_related('agent', 'agency', 'carrier'), pk=pk)


def search_passwords(passwords, search):
    """Narrow `passwords` to those whose username, agent, agency or carrier name matches."""
    return passwords.filter(
        Q(username__icontains=search)
        | Q(agent__name__icontains=search)
        | Q(agency__name__icontains=search)
        | Q(carrier__name__icontains=search)
    )


def filter_passwords(passwords, agent_id=None, agency_id=None, carrier_id=None, status=None):
    """Narrow `passwords` by agent, agency, carrier and status; None means no filter."""
    if agent_id is not None:
        passwords = passwords.filter(agent_id=agent_id)
    if agency_id is not None:
        passwords = passwords.filter(agency_id=agency_id)
    if carrier_id is not None:
        passwords = passwords.filter(carrier_id=carrier_id)
    if status:
        passwords = passwords.filter(status=status)
    return passwords


def save_password(password, actor, **fields):
    """Set `fields` on the password and record `actor` as updated_by."""
    for name, value in fields.items():
        setattr(password, name, value)
    password.updated_by = actor
    password.save(update_fields=[*fields, 'updated_by'])
    return password


def snapshot(password):
    """The password's fields as a note compares them: the agent (or the
    agency) and carrier by name. The portal password is compared but never
    written to a note."""
    return {
        'agent': password.party.name,
        'carrier': password.carrier.name,
        'username': password.username,
        'password': password.portal_password,
        'link': password.link,
        'status': password.status,
    }


def diff_snapshots(before, after):
    """Fields whose value differs, in NOTE_FIELDS order; redacted fields say
    only that they changed. `before` is {} for a new password."""
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


def record_note(password, actor, kind, changes):
    """Append a change note. Nothing is written when there are no changes."""
    if not changes:
        return None
    return PasswordNote.objects.create(
        password=password,
        kind=kind,
        changes=changes,
        created_by=actor,
        updated_by=actor,
    )
