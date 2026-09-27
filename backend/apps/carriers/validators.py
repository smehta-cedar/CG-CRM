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


def resolve_states(codes):
    """The State rows for `codes` (two-letter, any case). Unknown codes are a 400."""
    wanted = {code.strip().upper() for code in codes if code and code.strip()}
    states = list(State.objects.filter(code__in=wanted))
    unknown = sorted(wanted - {state.code for state in states})
    if unknown:
        raise ValidationError({'available_states': [f"Unknown state code: {', '.join(unknown)}."]})
    return states
