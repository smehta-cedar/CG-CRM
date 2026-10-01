import datetime
import os

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404

from apps.policies.models import (
    CarrierPolicy,
    CarrierPolicyNote,
    Certification,
    CertificationNote,
    PolicyType,
    PolicyTypeNote,
)

# Helpers the policies views share. Checks that can reject a request live in
# apps.policies.validators instead.


def normalize_name(name):
    return ' '.join(name.split())


def diff_snapshots(before, after, fields):
    """Fields whose shown value differs, in `fields` order.
    `before` is {} for a new row, so every filled field is listed."""
    changes = []
    for field in fields:
        from_value = before.get(field, '')
        to_value = after.get(field, '')
        if from_value != to_value:
            changes.append({'field': field, 'from': from_value, 'to': to_value})
    return changes


# --- policy types -----------------------------------------------------------

# The order a policy type note lists changed fields in.
NOTE_FIELDS = ('name', 'status')


def policy_type_queryset():
    return PolicyType.objects.all()


def get_policy_type_or_404(pk):
    return get_object_or_404(policy_type_queryset(), pk=pk)


def search_policy_types(policy_types, search):
    """Narrow `policy_types` to those whose name matches."""
    return policy_types.filter(name__icontains=search)


def filter_policy_types(policy_types, is_active=None):
    """Narrow `policy_types` by is_active; None means no filter."""
    if is_active is not None:
        policy_types = policy_types.filter(is_active=is_active)
    return policy_types


def save_policy_type(policy_type, actor, **fields):
    """Set `fields` on the policy type and record `actor` as updated_by."""
    for name, value in fields.items():
        setattr(policy_type, name, value)
    policy_type.updated_by = actor
    policy_type.save(update_fields=[*fields, 'updated_by'])
    return policy_type


def snapshot(policy_type):
    """The policy type's fields as a note shows them: the status as
    "active" / "inactive". Compare two of these to find what changed."""
    return {
        'name': policy_type.name,
        'status': 'active' if policy_type.is_active else 'inactive',
    }


def record_note(policy_type, actor, kind, changes):
    """Append a change note. Nothing is written when there are no changes."""
    if not changes:
        return None
    return PolicyTypeNote.objects.create(
        policy_type=policy_type,
        kind=kind,
        changes=changes,
        created_by=actor,
        updated_by=actor,
    )


# --- carrier policies -------------------------------------------------------

# The order a carrier policy note lists changed fields in.
POLICY_NOTE_FIELDS = ('name', 'policy_type', 'carrier', 'available_states', 'status')


def policy_queryset():
    return CarrierPolicy.objects.select_related('carrier', 'policy_type').prefetch_related('available_states')


def get_policy_or_404(pk):
    return get_object_or_404(policy_queryset(), pk=pk)


def search_policies(policies, search):
    """Narrow `policies` to those whose name matches."""
    return policies.filter(name__icontains=search)


def filter_policies(policies, carrier=None, policy_type=None, is_active=None):
    """Narrow `policies` by carrier, policy type and is_active; None means no filter."""
    if carrier is not None:
        policies = policies.filter(carrier_id=carrier)
    if policy_type is not None:
        policies = policies.filter(policy_type_id=policy_type)
    if is_active is not None:
        policies = policies.filter(is_active=is_active)
    return policies


def save_policy(policy, actor, states=None, **fields):
    """Set `fields` on the policy, replace its states when `states` is given,
    and record `actor` as updated_by."""
    for name, value in fields.items():
        setattr(policy, name, value)
    policy.updated_by = actor
    policy.save(update_fields=[*fields, 'updated_by'])
    if states is not None:
        policy.available_states.set(states)
    return policy


def policy_snapshot(policy):
    """The policy's fields as a note shows them: the type and carrier by
    name, states joined with ", ", the status as "active" / "inactive".
    Compare two of these to find what changed."""
    return {
        'name': policy.name,
        'policy_type': policy.policy_type.name,
        'carrier': policy.carrier.name,
        'available_states': ', '.join(policy.state_codes),
        'status': 'active' if policy.is_active else 'inactive',
    }


def record_policy_note(policy, actor, kind, changes):
    """Append a change note. Nothing is written when there are no changes."""
    if not changes:
        return None
    return CarrierPolicyNote.objects.create(
        policy=policy,
        kind=kind,
        changes=changes,
        created_by=actor,
        updated_by=actor,
    )


# --- certifications ---------------------------------------------------------


def certification_due_date(today=None):
    """The next certification deadline on or after `today` (default: today),
    on settings.CERTIFICATION_DUE_MONTH / _DAY."""
    today = today or timezone.localdate()
    due = datetime.date(today.year, settings.CERTIFICATION_DUE_MONTH, settings.CERTIFICATION_DUE_DAY)
    return due if due >= today else due.replace(year=today.year + 1)


# The order a certification note lists changed fields in.
CERTIFICATION_NOTE_FIELDS = (
    'agent',
    'carrier',
    'line_of_business',
    'due_date',
    'start_date',
    'end_date',
    'is_verified',
    'status',
    'file',
)


def certification_queryset():
    return Certification.objects.select_related('agent', 'carrier')


def get_certification_or_404(pk):
    return get_object_or_404(certification_queryset(), pk=pk)


def filter_certifications(certifications, agent=None, carrier=None, line_of_business=None):
    """Narrow `certifications` by agent, carrier and line of business; None means no filter."""
    if agent is not None:
        certifications = certifications.filter(agent_id=agent)
    if carrier is not None:
        certifications = certifications.filter(carrier_id=carrier)
    if line_of_business is not None:
        certifications = certifications.filter(line_of_business=line_of_business)
    return certifications


def save_certification(certification, actor, **fields):
    """Set `fields` on the certification and record `actor` as updated_by."""
    for name, value in fields.items():
        setattr(certification, name, value)
    certification.updated_by = actor
    certification.save(update_fields=[*fields, 'updated_by'])
    return certification


def certification_snapshot(certification):
    """The certification's fields as a note shows them: the agent and carrier
    by name (carrier blank when there is none), dates as YYYY-MM-DD or blank,
    the verified flag as "yes" / "no", the status as "active" / "inactive",
    the PDF by its file name only (blank when there is none). Compare two of
    these to find what changed."""
    return {
        'agent': certification.agent.name,
        'carrier': certification.carrier.name if certification.carrier else '',
        'line_of_business': certification.line_of_business,
        'due_date': certification.due_date.isoformat() if certification.due_date else '',
        'start_date': certification.start_date.isoformat() if certification.start_date else '',
        'end_date': certification.end_date.isoformat() if certification.end_date else '',
        'is_verified': 'yes' if certification.is_verified else 'no',
        'status': 'active' if certification.is_active else 'inactive',
        'file': certification.file_name if certification.file else '',
    }


def add_contract_certifications(agent, carrier, actor=None, due_date=None):
    """Give `agent` one certification per line of business `carrier` writes,
    due on `due_date` (default: the next deadline), and return the rows made
    or filled in. Lines the agent already has with this carrier for that
    deadline are skipped. A row with this carrier and no due date counts for
    that deadline: one with a line just takes the date, one with no line
    takes a missing line (and the date) before a new row is made. Each row
    gets an "added" note, or "edited" for one filled in."""
    due_date = due_date or certification_due_date()
    rows = list(
        Certification.objects.filter(agent=agent, carrier=carrier)
        .filter(models.Q(due_date=due_date) | models.Q(due_date__isnull=True))
        .select_related('agent', 'carrier')
        .order_by('created_at')
    )
    touched = []

    def fill_in(certification, **fields):
        before = certification_snapshot(certification)
        save_certification(certification, actor, **fields)
        record_certification_note(
            certification,
            actor,
            CertificationNote.KIND_EDITED,
            diff_snapshots(before, certification_snapshot(certification), CERTIFICATION_NOTE_FIELDS),
        )
        touched.append(certification)

    # Undated rows that already have a line keep it and take the deadline.
    for certification in rows:
        if certification.line_of_business and certification.due_date is None:
            fill_in(certification, due_date=due_date)

    have = {row.line_of_business for row in rows if row.line_of_business}
    blank = [row for row in rows if not row.line_of_business]
    for line in carrier.lines_of_business:
        if line in have:
            continue
        if blank:
            fill_in(blank.pop(0), line_of_business=line, due_date=due_date)
        else:
            certification = Certification.objects.create(
                agent=agent,
                carrier=carrier,
                line_of_business=line,
                due_date=due_date,
                created_by=actor,
                updated_by=actor,
            )
            record_certification_note(
                certification,
                actor,
                CertificationNote.KIND_ADDED,
                diff_snapshots({}, certification_snapshot(certification), CERTIFICATION_NOTE_FIELDS),
            )
            touched.append(certification)
    return touched


def upload_name(upload):
    """The name a file was uploaded with, as `file_name` stores it."""
    return os.path.basename(upload.name)[:255]


def delete_file_on_commit(field_file, name):
    """Remove the stored file `name` once the transaction commits, e.g. the
    PDF a new upload just replaced."""
    storage = field_file.storage
    transaction.on_commit(lambda: storage.delete(name))


def record_certification_note(certification, actor, kind, changes):
    """Append a change note. Nothing is written when there are no changes."""
    if not changes:
        return None
    return CertificationNote.objects.create(
        certification=certification,
        kind=kind,
        changes=changes,
        created_by=actor,
        updated_by=actor,
    )
