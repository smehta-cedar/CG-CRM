from rest_framework.exceptions import ValidationError

from apps.agency.models import State
from apps.carriers.models import Carrier

# Every check the carrier views run. Each one returns nothing when the check
# passes and raises ValidationError (400, field errors under "errors").


def ensure_name_free(name, exclude=None):
    """A name can't repeat another live carrier's name or alias, ignoring case."""
    key = name.lower()
    carriers = Carrier.objects.all()
    if exclude is not None:
        carriers = carriers.exclude(pk=exclude.pk)
    if carriers.filter(name__iexact=name).exists():
        raise ValidationError({'name': ['A carrier with this name already exists.']})
    # Aliases sit in a JSON list, so the case-insensitive match runs here.
    for carrier in carriers.exclude(aliases=[]).only('name', 'aliases'):
        if any(alias.lower() == key for alias in carrier.aliases):
            raise ValidationError({'name': [f'{name} is already an alias of {carrier.name}.']})


def ensure_aliases_free(aliases, name, exclude=None):
    """An alias can't repeat the carrier's own name or another live carrier's
    name or alias, ignoring case."""
    keys = {alias.lower() for alias in aliases}
    if not keys:
        return
    if name.lower() in keys:
        raise ValidationError({'aliases': ['An alias cannot repeat the carrier name.']})
    carriers = Carrier.objects.all()
    if exclude is not None:
        carriers = carriers.exclude(pk=exclude.pk)
    for carrier in carriers.only('name', 'aliases'):
        taken = {carrier.name.lower(), *(alias.lower() for alias in carrier.aliases)}
        clash = keys & taken
        if clash:
            raise ValidationError({'aliases': [f'{sorted(clash)[0]} already belongs to {carrier.name}.']})


def ensure_lines_chosen(lines):
    if not lines:
        raise ValidationError({'lines_of_business': ['Choose at least one line of business.']})


# What a state row gets for a field left out. A PATCH (partial) skips the
# input serializer's own defaults, so they are filled in here.
LICENSE_DEFAULTS = {
    'license_number': '',
    'status': 'active',
    'start_date': None,
    'end_date': None,
    'life': False,
    'health': False,
}


def resolve_licenses(licenses):
    """The `licenses` input with each two-letter code swapped for its State,
    ready for utils.sync_licenses. Unknown codes are a 400; a repeated state
    keeps its last entry."""
    wanted = {}
    for item in licenses:
        wanted[item['state'].strip().upper()] = item
    states = {state.code: state for state in State.objects.filter(code__in=wanted)}
    unknown = sorted(set(wanted) - set(states))
    if unknown:
        raise ValidationError({'licenses': [f"Unknown state code: {', '.join(unknown)}."]})
    return [{**LICENSE_DEFAULTS, **item, 'state': states[code]} for code, item in wanted.items()]
