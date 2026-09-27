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
    """(State, number) pairs for a list of {"state", "license_number"}; unknown
    codes are a 400 and a repeated state keeps its last number."""
    if not licenses:
        return []
    wanted = {}
    for item in licenses:
        code = item['state'].strip().upper()
        wanted[code] = item.get('license_number', '')
    states = {state.code: state for state in State.objects.filter(code__in=wanted)}
    unknown = sorted(set(wanted) - set(states))
    if unknown:
        raise ValidationError({'licenses': [f"Unknown state code: {', '.join(unknown)}."]})
    return [(states[code], number) for code, number in wanted.items()]


def ensure_npn_free(npn, exclude=None):
    if not npn:
        return
    agencies = Agency.objects.filter(npn=npn)
    if exclude is not None:
        agencies = agencies.exclude(pk=exclude.pk)
    if agencies.exists():
        raise ValidationError({'npn': ['An agency with this NPN already exists.']})
