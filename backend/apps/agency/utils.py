from datetime import date

from django.db.models import Q
from django.shortcuts import get_object_or_404

from apps.agency.models import Agency, AgencyNote, AgencyStateLicense

# Helpers the agency views share. Checks that can reject a request live in
# apps.agency.validators instead.


# The order a note lists changed fields in.
NOTE_FIELDS = (
    'name',
    'aliases',
    'status',
    'npn',
    'email',
    'phone',
    'licensed_states',
    'license_numbers',
    'license_lines',
    'license_statuses',
    'license_dates',
)

def get_agency_or_404(pk):
    return get_object_or_404(Agency.objects.prefetch_related('licenses__state'), pk=pk)


def normalize_name(name):
    return ' '.join(name.split())


def normalize_npn(npn):
    return npn.strip()


def normalize_email(email):
    return email.strip().lower()


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


def search_agencies(agencies, search):
    """Narrow `agencies` to those whose name, alias, NPN, email or phone matches."""
    return agencies.filter(
        Q(name__icontains=search)
        | Q(aliases__icontains=search)
        | Q(npn__icontains=search)
        | Q(email__icontains=search)
        | Q(phone__icontains=search)
    )


def filter_agencies(agencies, is_active=None):
    """Narrow `agencies` by is_active; None means no filter."""
    if is_active is not None:
        agencies = agencies.filter(is_active=is_active)
    return agencies


def save_agency(agency, actor, **fields):
    """Set `fields` on the agency and record `actor` as updated_by."""
    for name, value in fields.items():
        setattr(agency, name, value)
    agency.updated_by = actor
    agency.save(update_fields=[*fields, 'updated_by'])
    return agency


def live_licenses(agency):
    """The agency's licence rows, in state-code order."""
    return sorted(agency.licenses.all(), key=lambda row: row.state.code)


def sync_licenses(agency, actor, wanted, today=None):
    """Make the agency's licence rows match `wanted`, a list of
    (State, number, life, health, status, start_date, end_date).

    A state already licensed keeps its row, with the number and lines as
    given and the status and dates as given (a None status or date leaves
    the row's alone); a state no longer listed loses its row (soft delete);
    a new state gets a row with the status given (active when None) and the
    dates given: starting today when the start is None, and with no end
    date when the end is None.
    """
    today = today or date.today()
    wanted_by_state = {
        state.pk: (state, number.strip(), bool(life), bool(health), status, start, end, renewing)
        for state, number, life, health, status, start, end, renewing in wanted
    }

    for row in list(agency.licenses.all()):
        if row.state_id not in wanted_by_state:
            row.delete(user=actor)
            continue
        _, number, life, health, status, start, end, renewing = wanted_by_state.pop(row.state_id)
        updates = {'license_number': number, 'life': life, 'health': health}
        if status is not None:
            updates['status'] = status
        if renewing is not None:
            updates['renewing'] = renewing
        if start is not None:
            updates['start_date'] = start
        if end is not None:
            updates['end_date'] = end
        changed = [field for field, value in updates.items() if getattr(row, field) != value]
        if changed:
            for field in changed:
                setattr(row, field, updates[field])
            row.updated_by = actor
            row.save(update_fields=[*changed, 'updated_by'])

    for state, number, life, health, status, start, end, renewing in wanted_by_state.values():
        start = start or today
        AgencyStateLicense.objects.create(
            agency=agency,
            state=state,
            license_number=number,
            life=life,
            health=health,
            status=status or 'active',
            start_date=start,
            end_date=end,
            renewing=bool(renewing),
            created_by=actor,
            updated_by=actor,
        )


def snapshot(agency):
    """The agency's fields as a note shows them. Reads the licence rows, so
    call it on a fresh agency."""
    licenses = live_licenses(agency)
    return {
        'name': agency.name,
        'aliases': ', '.join(agency.aliases),
        'status': 'active' if agency.is_active else 'inactive',
        'npn': agency.npn,
        'email': agency.email,
        'phone': agency.phone,
        'licensed_states': ', '.join(row.state.code for row in licenses),
        'license_numbers': ', '.join(
            f'{row.state.code} {row.license_number}' for row in licenses if row.license_number
        ),
        # "TX Life & Health, FL Health": only the rows with a line ticked.
        'license_lines': ', '.join(
            f'{row.state.code} {row.lines_text}' for row in licenses if row.lines_text
        ),
        # "FL active, TX pending": every row.
        'license_statuses': ', '.join(f'{row.state.code} {row.status}' for row in licenses),
        # "TX 2026-01-01 to 2028-01-01": only the rows with a date.
        'license_dates': ', '.join(
            f'{row.state.code} {row.start_date or "?"} to {row.end_date or "?"}'
            for row in licenses
            if row.start_date or row.end_date
        ),
    }


def diff_snapshots(before, after):
    """Fields whose shown value differs, in NOTE_FIELDS order.
    `before` is {} for a new agency, so only its filled fields are listed."""
    changes = []
    for field in NOTE_FIELDS:
        from_value = before.get(field, '')
        to_value = after.get(field, '')
        if from_value != to_value:
            changes.append({'field': field, 'from': from_value, 'to': to_value})
    return changes


def record_note(agency, actor, kind, changes):
    """Append a change note. Nothing is written when there are no changes."""
    if not changes:
        return None
    return AgencyNote.objects.create(
        agency=agency,
        kind=kind,
        changes=changes,
        created_by=actor,
        updated_by=actor,
    )
