from rest_framework.exceptions import ValidationError

from apps.agency.models import Agency, State

# Every check the agency views run. Each one returns nothing when the check
# passes and raises ValidationError (400, field errors under "errors").


def ensure_name_free(name, exclude=None):
    # Agency.objects: a deleted agency's name may be reused.
    agencies = Agency.objects.filter(name__iexact=name)
    if exclude is not None:
        agencies = agencies.exclude(pk=exclude.pk)
    if agencies.exists():
        raise ValidationError({'name': ['An agency with this name already exists.']})


def resolve_licenses(licenses):
    """(State, number, status, start_date, end_date) tuples for a list of
    {"state", "license_number", "status", "start_date", "end_date"}; unknown
    codes are a 400 and a repeated state keeps its last entry. A missing
    status or date is None: sync_licenses defaults it for a new row and
    leaves it alone on a kept one."""
    if not licenses:
        return []
    wanted = {}
    for item in licenses:
        code = item['state'].strip().upper()
        wanted[code] = (
            item.get('license_number', ''),
            item.get('status'),
            item.get('start_date'),
            item.get('end_date'),
        )
    states = {state.code: state for state in State.objects.filter(code__in=wanted)}
    unknown = sorted(set(wanted) - set(states))
    if unknown:
        raise ValidationError({'licenses': [f"Unknown state code: {', '.join(unknown)}."]})
    return [(states[code], *rest) for code, rest in wanted.items()]


def ensure_npn_free(npn, exclude=None):
    if not npn:
        return
    agencies = Agency.objects.filter(npn=npn)
    if exclude is not None:
        agencies = agencies.exclude(pk=exclude.pk)
    if agencies.exists():
        raise ValidationError({'npn': ['An agency with this NPN already exists.']})
