from datetime import date

from django.db.models import Q
from django.shortcuts import get_object_or_404

from apps.agents.models import Agent, AgentNote, AgentStateLicense

# Helpers the agent views share. Checks that can reject a request live in
# apps.agents.validators instead.

# The order a note lists changed fields in.
NOTE_FIELDS = (
    'name',
    'aliases',
    'status',
    'npn',
    'email',
    'phone',
    'personal_email',
    'personal_phone',
    'address',
    'licensed_states',
    'license_numbers',
)

# How long a new licence runs from its start date, until the form asks for dates.
LICENSE_TERM_YEARS = 2


def get_agent_or_404(pk):
    return get_object_or_404(Agent.objects.prefetch_related('licenses__state'), pk=pk)


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


def address_fields(address):
    """The four address_* columns for an address dict, or blanks for None."""
    address = address or {}
    return {
        'address_street': ' '.join(address.get('street', '').split()),
        'address_city': ' '.join(address.get('city', '').split()),
        'address_state': address.get('state', '').strip().upper(),
        'address_zip': address.get('zip', '').strip(),
    }


def address_text(agent):
    """"1420 Cedar Grove Ln, Austin, TX 78704", how notes show it; "" when none."""
    address = agent.address
    if not address:
        return ''
    parts = [address['street'], address['city'], f"{address['state']} {address['zip']}".strip()]
    return ', '.join(part for part in parts if part)


def live_licenses(agent):
    """The agent's licence rows, in state-code order."""
    return sorted(agent.licenses.all(), key=lambda row: row.state.code)


def search_agents(agents, search):
    """Narrow `agents` to those whose name, alias, NPN, email or phone matches."""
    return agents.filter(
        Q(name__icontains=search)
        | Q(aliases__icontains=search)
        | Q(npn__icontains=search)
        | Q(email__icontains=search)
        | Q(phone__icontains=search)
        | Q(personal_email__icontains=search)
        | Q(personal_phone__icontains=search)
    )


def filter_agents(agents, is_active=None, state=None):
    """Narrow `agents` by is_active and by a licensed state code; None means no filter."""
    if is_active is not None:
        agents = agents.filter(is_active=is_active)
    if state:
        agents = agents.filter(
            licenses__state__code=state.upper(),
            licenses__deleted_at__isnull=True,
        ).distinct()
    return agents


def save_agent(agent, actor, **fields):
    """Set `fields` on the agent and record `actor` as updated_by."""
    for name, value in fields.items():
        setattr(agent, name, value)
    agent.updated_by = actor
    agent.save(update_fields=[*fields, 'updated_by'])
    return agent


def sync_licenses(agent, actor, wanted, today=None):
    """Make the agent's licence rows match `wanted`, a list of (State, number).

    A state already licensed keeps its row, with the number as given; a
    state no longer listed loses its row (soft delete); a new state gets an
    active row starting today and running LICENSE_TERM_YEARS. Statuses and
    dates of kept rows are untouched.
    """
    today = today or date.today()
    end = today.replace(year=today.year + LICENSE_TERM_YEARS)
    wanted_by_state = {state.pk: (state, number.strip()) for state, number in wanted}

    for row in list(agent.licenses.all()):
        if row.state_id not in wanted_by_state:
            row.delete(user=actor)
            continue
        _, number = wanted_by_state.pop(row.state_id)
        if number != row.license_number:
            row.license_number = number
            row.updated_by = actor
            row.save(update_fields=['license_number', 'updated_by'])

    for state, number in wanted_by_state.values():
        AgentStateLicense.objects.create(
            agent=agent,
            state=state,
            license_number=number,
            status='active',
            start_date=today,
            end_date=end,
            created_by=actor,
            updated_by=actor,
        )


def snapshot(agent):
    """The agent's fields as a note shows them. Compare two of these to find
    what changed. Reads the licence rows, so call it on a fresh agent."""
    licenses = live_licenses(agent)
    return {
        'name': agent.name,
        'aliases': ', '.join(agent.aliases),
        'status': 'active' if agent.is_active else 'inactive',
        'npn': agent.npn,
        'email': agent.email,
        'phone': agent.phone,
        'personal_email': agent.personal_email,
        'personal_phone': agent.personal_phone,
        'address': address_text(agent),
        'licensed_states': ', '.join(row.state.code for row in licenses),
        'license_numbers': ', '.join(
            f'{row.state.code} {row.license_number}' for row in licenses if row.license_number
        ),
    }


def diff_snapshots(before, after):
    """Fields whose shown value differs, in NOTE_FIELDS order.
    `before` is {} for a new agent, so only its filled fields are listed."""
    changes = []
    for field in NOTE_FIELDS:
        from_value = before.get(field, '')
        to_value = after.get(field, '')
        if from_value != to_value:
            changes.append({'field': field, 'from': from_value, 'to': to_value})
    return changes


def record_note(agent, actor, kind, changes):
    """Append a change note. Nothing is written when there are no changes."""
    if not changes:
        return None
    return AgentNote.objects.create(
        agent=agent,
        kind=kind,
        changes=changes,
        created_by=actor,
        updated_by=actor,
    )
