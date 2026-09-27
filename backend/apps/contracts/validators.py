from rest_framework.exceptions import ValidationError

from apps.agency.models import State
from apps.contracts.models import CarrierContract

# Every check the contract views run. Each one returns nothing when the check
# passes and raises ValidationError (400, field errors under "errors").


def ensure_pair_free(agent, carrier, exclude=None):
    """One contract per agent at each carrier."""
    contracts = CarrierContract.objects.filter(agent=agent, carrier=carrier)
    if exclude is not None:
        contracts = contracts.exclude(pk=exclude.pk)
    if contracts.exists():
        raise ValidationError({'agent_id': [f'{agent.name} already has a contract with {carrier.name}.']})


def ensure_writing_number_free(writing_number, carrier, exclude=None):
    """A writing number is unique within a carrier, ignoring case. Blank means none yet."""
    if not writing_number:
        return
    contracts = CarrierContract.objects.filter(carrier=carrier, writing_number__iexact=writing_number)
    if exclude is not None:
        contracts = contracts.exclude(pk=exclude.pk)
    owner = contracts.select_related('agent').first()
    if owner is not None:
        raise ValidationError({
            'writing_number': [
                f'Writing number {owner.writing_number} is already used at {carrier.name} by {owner.agent.name}.'
            ]
        })


def resolve_states(codes):
    """The State rows for `codes` (two-letter, any case). Unknown codes are a 400."""
    wanted = {code.strip().upper() for code in codes if code and code.strip()}
    states = list(State.objects.filter(code__in=wanted))
    unknown = sorted(wanted - {state.code for state in states})
    if unknown:
        raise ValidationError({'appointed_states': [f"Unknown state code: {', '.join(unknown)}."]})
    return states


def ensure_within_ceiling(states, agent, carrier):
    """Every appointed state must be one the carrier is available in and the
    agent is licensed in. Each half is checked on its own, so the error names
    the side that blocks the state and the page that fixes it."""
    codes = sorted(state.code for state in states)
    available = {state.code for state in carrier.available_states.all()}
    unavailable = [code for code in codes if code not in available]
    if unavailable:
        them = 'it' if len(unavailable) == 1 else 'them'
        raise ValidationError({
            'appointed_states': [
                f"{carrier.name} isn't available in {', '.join(unavailable)}. "
                f"Add {them} to the carrier's states on Carriers first."
            ]
        })
    licensed = {row.state.code for row in agent.licenses.all()}
    unlicensed = [code for code in codes if code not in licensed]
    if unlicensed:
        them = 'it' if len(unlicensed) == 1 else 'them'
        raise ValidationError({
            'appointed_states': [
                f"{agent.name} isn't licensed in {', '.join(unlicensed)}. "
                f"Add {them} to their licensed states on Agents first."
            ]
        })
