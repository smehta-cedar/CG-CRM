from django.db.models import Q
from django.shortcuts import get_object_or_404

from apps.carriers.models import LINES_OF_BUSINESS, Carrier, CarrierNote

# Helpers the carrier views share. Checks that can reject a request live in
# apps.carriers.validators instead.

# The order a note lists changed fields in.
NOTE_FIELDS = ('name', 'aliases', 'lines_of_business', 'available_states', 'status')


def get_carrier_or_404(pk):
    return get_object_or_404(Carrier.objects.prefetch_related('available_states'), pk=pk)


def normalize_name(name):
    return ' '.join(name.split())


def normalize_aliases(aliases):
    """Trim each alias, drop blanks, and keep the first of any duplicates
    (compared case-insensitively) in the order given."""
    seen = set()
    result = []
    for alias in aliases:
        alias = ' '.join(alias.split())
        key = alias.lower()
        if alias and key not in seen:
            seen.add(key)
            result.append(alias)
    return result


def normalize_lines(lines):
    """Unique lines of business, in LINES_OF_BUSINESS order."""
    chosen = set(lines)
    return [line for line in LINES_OF_BUSINESS if line in chosen]


def search_carriers(carriers, search):
    """Narrow `carriers` to those whose name, alias or line of business matches."""
    return carriers.filter(
        Q(name__icontains=search)
        | Q(aliases__icontains=search)
        | Q(lines_of_business__icontains=search)
    )


def filter_carriers(carriers, is_active=None, state=None):
    """Narrow `carriers` by is_active and by a state code; None means no filter."""
    if is_active is not None:
        carriers = carriers.filter(is_active=is_active)
    if state:
        carriers = carriers.filter(available_states__code=state.upper())
    return carriers


def save_carrier(carrier, actor, states=None, **fields):
    """Set `fields` on the carrier, replace its states when `states` is given,
    and record `actor` as updated_by."""
    for name, value in fields.items():
        setattr(carrier, name, value)
    carrier.updated_by = actor
    carrier.save(update_fields=[*fields, 'updated_by'])
    if states is not None:
        carrier.available_states.set(states)
    return carrier


def snapshot(carrier):
    """The carrier's fields as a note shows them: lists joined with ", ",
    the status as "active" / "inactive". Compare two of these to find what
    changed."""
    return {
        'name': carrier.name,
        'aliases': ', '.join(carrier.aliases),
        'lines_of_business': ', '.join(carrier.lines_of_business),
        'available_states': ', '.join(carrier.state_codes),
        'status': 'active' if carrier.is_active else 'inactive',
    }


def diff_snapshots(before, after):
    """Fields whose shown value differs, in NOTE_FIELDS order.
    `before` is {} for a new carrier, so only its filled fields are listed."""
    changes = []
    for field in NOTE_FIELDS:
        from_value = before.get(field, '')
        to_value = after.get(field, '')
        if from_value != to_value:
            changes.append({'field': field, 'from': from_value, 'to': to_value})
    return changes


def record_note(carrier, actor, kind, changes):
    """Append a change note. Nothing is written when there are no changes."""
    if not changes:
        return None
    return CarrierNote.objects.create(
        carrier=carrier,
        kind=kind,
        changes=changes,
        created_by=actor,
        updated_by=actor,
    )
