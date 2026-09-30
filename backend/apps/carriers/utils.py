from django.db.models import Q
from django.shortcuts import get_object_or_404

from apps.carriers.models import LINES_OF_BUSINESS, Carrier, CarrierNote, CarrierStateLicense

# Helpers the carrier views share. Checks that can reject a request live in
# apps.carriers.validators instead.

# The order a note lists changed fields in.
NOTE_FIELDS = (
    'name',
    'aliases',
    'lines_of_business',
    'link',
    'available_states',
    'license_numbers',
    'license_statuses',
    'license_lines',
    'license_dates',
    'status',
)


def get_carrier_or_404(pk):
    return get_object_or_404(Carrier.objects.prefetch_related('available_states', 'licenses__state'), pk=pk)


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


def save_carrier(carrier, actor, licenses=None, **fields):
    """Set `fields` on the carrier, replace its state rows when `licenses` is
    given (see sync_licenses), and record `actor` as updated_by."""
    for name, value in fields.items():
        setattr(carrier, name, value)
    carrier.updated_by = actor
    carrier.save(update_fields=[*fields, 'updated_by'])
    if licenses is not None:
        sync_licenses(carrier, actor, licenses)
    return carrier


def live_licenses(carrier):
    """The carrier's state rows, in state-code order."""
    return sorted(carrier.licenses.all(), key=lambda row: row.state.code)


def sync_licenses(carrier, actor, wanted):
    """Make the carrier's state rows match `wanted`, a list of dicts with
    state (a State), license_number, status, start_date, end_date, life and
    health, then set available_states to their states.

    A state already listed keeps its row with the values given; a state no
    longer listed loses its row (soft delete); a new state gets a row.
    """
    wanted_by_state = {item['state'].pk: item for item in wanted}
    fields = ('license_number', 'status', 'start_date', 'end_date', 'life', 'health')

    for row in list(carrier.licenses.all()):
        item = wanted_by_state.pop(row.state_id, None)
        if item is None:
            row.delete(user=actor)
            continue
        changed = [field for field in fields if getattr(row, field) != item[field]]
        if changed:
            for field in changed:
                setattr(row, field, item[field])
            row.updated_by = actor
            row.save(update_fields=[*changed, 'updated_by'])

    for item in wanted_by_state.values():
        CarrierStateLicense.objects.create(
            carrier=carrier,
            **{field: item[field] for field in ('state', *fields)},
            created_by=actor,
            updated_by=actor,
        )

    carrier.available_states.set([item['state'] for item in wanted])


def snapshot(carrier):
    """The carrier's fields as a note shows them: lists joined with ", ",
    the status as stored ("active", "pending", …). Compare two of these to find
    what changed. Reads the state rows, so call it on a fresh carrier."""
    licenses = live_licenses(carrier)
    return {
        'name': carrier.name,
        'aliases': ', '.join(carrier.aliases),
        'lines_of_business': ', '.join(carrier.lines_of_business),
        'link': carrier.link,
        'available_states': ', '.join(carrier.state_codes),
        'license_numbers': ', '.join(
            f'{row.state.code} {row.license_number}' for row in licenses if row.license_number
        ),
        'license_statuses': ', '.join(f'{row.state.code} {row.status}' for row in licenses),
        # "FL Health, TX Life & Health": only the states with a line ticked.
        'license_lines': ', '.join(
            f'{row.state.code} {row.lines_text}' for row in licenses if row.lines_text
        ),
        # "TX 2026-01-01 to 2028-01-01": only the rows with a date.
        'license_dates': ', '.join(
            f'{row.state.code} {row.start_date or "?"} to {row.end_date or "?"}'
            for row in licenses
            if row.start_date or row.end_date
        ),
        'status': carrier.status,
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
