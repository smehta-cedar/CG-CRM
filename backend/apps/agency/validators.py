from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.agency.models import Agency, State
from apps.agents.models import Agent

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
    """(State, number, life, health, status, start_date, end_date, renewing)
    tuples for a list of {"state", "license_number", "life", "health",
    "status", "start_date", "end_date", "renewing"}; unknown codes are a 400
    and a repeated state keeps its last entry. A missing status, date or
    renewing is None: sync_licenses defaults it for a new row and leaves it
    alone on a kept one."""
    if not licenses:
        return []
    wanted = {}
    for item in licenses:
        code = item['state'].strip().upper()
        wanted[code] = (
            item.get('license_number', ''),
            bool(item.get('life')),
            bool(item.get('health')),
            item.get('status'),
            item.get('start_date'),
            item.get('end_date'),
            item.get('renewing'),
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


def resolve_agent_licenses(user, items):
    """(State, [Agent]) pairs for a list of {"state", "agents"}: the agents to
    license in each state. Unknown codes or agents are a 400 under
    "agent_licenses"; it needs the agents update permission (403)."""
    items = [item for item in items if item['agents']]
    if not items:
        return []
    if not user.has_permission('agents', 'update'):
        raise PermissionDenied("Your role can't change agents' licences.")
    codes = {item['state'].strip().upper() for item in items}
    states = {state.code: state for state in State.objects.filter(code__in=codes)}
    unknown = sorted(codes - set(states))
    if unknown:
        raise ValidationError({'agent_licenses': [f"Unknown state code: {', '.join(unknown)}."]})
    pks = {pk for item in items for pk in item['agents']}
    agents = {agent.pk: agent for agent in Agent.objects.filter(pk__in=pks)}
    if len(agents) != len(pks):
        raise ValidationError({'agent_licenses': ['Unknown agent.']})
    return [
        (states[item['state'].strip().upper()], [agents[pk] for pk in item['agents']])
        for item in items
    ]
