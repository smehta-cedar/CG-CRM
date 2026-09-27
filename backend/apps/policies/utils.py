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
NOTE_FIELDS = ('name', 'certification_required', 'status')


def get_policy_type_or_404(pk):
    return get_object_or_404(PolicyType, pk=pk)


def search_policy_types(policy_types, search):
    """Narrow `policy_types` to those whose name matches."""
    return policy_types.filter(name__icontains=search)


def filter_policy_types(policy_types, is_active=None, certification_required=None):
    """Narrow `policy_types` by is_active and the certification flag; None means no filter."""
    if is_active is not None:
        policy_types = policy_types.filter(is_active=is_active)
    if certification_required is not None:
        policy_types = policy_types.filter(certification_required=certification_required)
    return policy_types


def save_policy_type(policy_type, actor, **fields):
    """Set `fields` on the policy type and record `actor` as updated_by."""
    for name, value in fields.items():
        setattr(policy_type, name, value)
    policy_type.updated_by = actor
    policy_type.save(update_fields=[*fields, 'updated_by'])
    return policy_type


def snapshot(policy_type):
    """The policy type's fields as a note shows them: the certification flag
    as "yes" / "no", the status as "active" / "inactive". Compare two of
    these to find what changed."""
    return {
        'name': policy_type.name,
        'certification_required': 'yes' if policy_type.certification_required else 'no',
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

# The order a certification note lists changed fields in.
CERTIFICATION_NOTE_FIELDS = ('agent', 'policy_type', 'start_date', 'end_date', 'status')


def certification_queryset():
    return Certification.objects.select_related('agent', 'policy_type')


def get_certification_or_404(pk):
    return get_object_or_404(certification_queryset(), pk=pk)


def filter_certifications(certifications, agent=None, policy_type=None):
    """Narrow `certifications` by agent and policy type; None means no filter."""
    if agent is not None:
        certifications = certifications.filter(agent_id=agent)
    if policy_type is not None:
        certifications = certifications.filter(policy_type_id=policy_type)
    return certifications


def save_certification(certification, actor, **fields):
    """Set `fields` on the certification and record `actor` as updated_by."""
    for name, value in fields.items():
        setattr(certification, name, value)
    certification.updated_by = actor
    certification.save(update_fields=[*fields, 'updated_by'])
    return certification


def certification_snapshot(certification):
    """The certification's fields as a note shows them: the agent and policy
    type by name, dates as YYYY-MM-DD or blank, the status as "active" /
    "inactive". Compare two of these to find what changed."""
    return {
        'agent': certification.agent.name,
        'policy_type': certification.policy_type.name,
        'start_date': certification.start_date.isoformat() if certification.start_date else '',
        'end_date': certification.end_date.isoformat() if certification.end_date else '',
        'status': 'active' if certification.is_active else 'inactive',
    }


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
