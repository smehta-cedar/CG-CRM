from rest_framework.exceptions import ValidationError

from apps.agency.models import State
from apps.agents.models import Agent

# Every check the agent views run. Each one returns nothing when the check
# passes and raises ValidationError (400, field errors under "errors").


def ensure_npn_free(npn, exclude=None):
    agents = Agent.objects.filter(npn=npn)
    if exclude is not None:
        agents = agents.exclude(pk=exclude.pk)
    owner = agents.first()
    if owner is not None:
        raise ValidationError({'npn': [f'NPN {npn} already belongs to {owner.name}.']})


def ensure_login_email_free(email, exclude=None):
    """Agents sign in with their work email, so each one belongs to one agent. Blank emails are not checked."""
    if not email:
        return
    agents = Agent.objects.filter(email=email)
    if exclude is not None:
        agents = agents.exclude(pk=exclude.pk)
    owner = agents.first()
    if owner is not None:
        raise ValidationError({'email': [f'{email} already belongs to {owner.name}.']})


def ensure_name_free(name, exclude=None):
    agents = Agent.objects.filter(name__iexact=name)
    if exclude is not None:
        agents = agents.exclude(pk=exclude.pk)
    if agents.exists():
        raise ValidationError({'name': ['An agent with this name already exists.']})


def ensure_address_complete(address):
    """An address is all four parts or none."""
    if address is None:
        return
    missing = [part for part in ('street', 'city', 'state', 'zip') if not (address.get(part) or '').strip()]
    if missing and len(missing) < 4:
        raise ValidationError({'address': [f"Enter the {', '.join(missing)} too, or leave the whole address blank."]})


def resolve_state(code, field):
    """The State row for one code (any case). An unknown code is a 400 under `field`."""
    state = State.objects.filter(code=code.strip().upper()).first()
    if state is None:
        raise ValidationError({field: [f'Unknown state code: {code}.']})
    return state


def resolve_licenses(licenses):
    """(State, number, life, health, start_date, end_date) tuples for a list
    of {"state", "license_number", "life", "health", "start_date",
    "end_date"}; unknown codes are a 400 and a repeated state keeps its last
    entry. A missing date is None: sync_licenses defaults it for a new row
    and leaves it alone on a kept one."""
    if not licenses:
        return []
    wanted = {}
    for item in licenses:
        code = item['state'].strip().upper()
        wanted[code] = (
            item.get('license_number', ''),
            bool(item.get('life')),
            bool(item.get('health')),
            item.get('start_date'),
            item.get('end_date'),
        )
    states = {state.code: state for state in State.objects.filter(code__in=wanted)}
    unknown = sorted(set(wanted) - set(states))
    if unknown:
        raise ValidationError({'licenses': [f"Unknown state code: {', '.join(unknown)}."]})
    return [(states[code], *rest) for code, rest in wanted.items()]
