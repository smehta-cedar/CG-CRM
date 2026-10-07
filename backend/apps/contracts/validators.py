from rest_framework.exceptions import ValidationError

from apps.agency.models import Agency, State
from apps.carriers.models import Carrier
from apps.contracts.models import AgencyCarrierContract, CarrierContract
from apps.contracts.utils import is_agent_accessible
from apps.policies.models import PolicyType

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


def ensure_carrier_accessible(carrier):
    """Agents can only be given a carrier whose live agency contract has a
    contract number. Shared by the appointment and password APIs."""
    if not is_agent_accessible(carrier):
        raise ValidationError({'carrier': ['Add a contract number before an agent can use this carrier.']})


# --- agency contracts -------------------------------------------------------


def resolve_agency(pk):
    """The live agency with `pk`; an unknown one is a 400 under "agency"."""
    agency = Agency.objects.filter(pk=pk).first()
    if agency is None:
        raise ValidationError({'agency': ['Unknown agency.']})
    return agency


def resolve_carrier(pk):
    """The live carrier with `pk`; an unknown one is a 400 under "carrier"."""
    carrier = Carrier.objects.filter(pk=pk).first()
    if carrier is None:
        raise ValidationError({'carrier': ['Unknown carrier.']})
    return carrier


def ensure_carrier_free(carrier, exclude=None):
    """One live agency contract per carrier."""
    contracts = AgencyCarrierContract.objects.filter(carrier=carrier)
    if exclude is not None:
        contracts = contracts.exclude(pk=exclude.pk)
    if contracts.exists():
        raise ValidationError({'carrier': [f'{carrier.name} already has an agency contract.']})


def resolve_policy_types(pks):
    """The live PolicyType rows for `pks`. Policy types are an add-on, not a
    check: unknown or deleted ones are dropped, never a 400."""
    return list(PolicyType.objects.filter(pk__in=set(pks)))

