from django.db.models import Q
from django.shortcuts import get_object_or_404

from apps.contracts.models import CarrierContract, CarrierContractNote

# Helpers the contract views share. Checks that can reject a request live in
# apps.contracts.validators instead.

# The order a note lists changed fields in.
NOTE_FIELDS = ('agent', 'carrier', 'writing_number', 'appointed_states')


def get_contract_or_404(pk):
    return get_object_or_404(
        CarrierContract.objects.select_related('agent', 'carrier').prefetch_related('appointed_states'),
        pk=pk,
    )


def search_contracts(contracts, search):
    """Narrow `contracts` to those whose agent, carrier or writing number matches."""
    return contracts.filter(
        Q(agent__name__icontains=search)
        | Q(carrier__name__icontains=search)
        | Q(writing_number__icontains=search)
    )


def filter_contracts(contracts, agent_id=None, carrier_id=None, state=None):
    """Narrow `contracts` by agent, carrier and an appointed state code; None means no filter."""
    if agent_id is not None:
        contracts = contracts.filter(agent_id=agent_id)
    if carrier_id is not None:
        contracts = contracts.filter(carrier_id=carrier_id)
    if state:
        contracts = contracts.filter(appointed_states__code=state.upper())
    return contracts


def save_contract(contract, actor, states=None, **fields):
    """Set `fields` on the contract, replace its states when `states` is given,
    and record `actor` as updated_by."""
    for name, value in fields.items():
        setattr(contract, name, value)
    contract.updated_by = actor
    contract.save(update_fields=[*fields, 'updated_by'])
    if states is not None:
        contract.appointed_states.set(states)
    return contract


def snapshot(contract):
    """The contract's fields as a note shows them: agent and carrier by name,
    states as codes joined with ", "."""
    return {
        'agent': contract.agent.name,
        'carrier': contract.carrier.name,
        'writing_number': contract.writing_number,
        'appointed_states': ', '.join(contract.state_codes),
    }


def diff_snapshots(before, after):
    """Fields whose shown value differs, in NOTE_FIELDS order.
    `before` is {} for a new contract, so only its filled fields are listed."""
    changes = []
    for field in NOTE_FIELDS:
        from_value = before.get(field, '')
        to_value = after.get(field, '')
        if from_value != to_value:
            changes.append({'field': field, 'from': from_value, 'to': to_value})
    return changes


def record_note(contract, actor, kind, changes):
    """Append a change note. Nothing is written when there are no changes."""
    if not changes:
        return None
    return CarrierContractNote.objects.create(
        contract=contract,
        kind=kind,
        changes=changes,
        created_by=actor,
        updated_by=actor,
    )
