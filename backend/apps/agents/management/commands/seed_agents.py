import json
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.agency.models import State
from apps.agents.models import LICENSE_STATUSES, Agent, AgentStateLicense
from apps.agents.utils import address_fields, normalize_aliases, normalize_name

# backend/apps/agents/management/commands -> repo root
REPO_ROOT = Path(__file__).resolve().parents[5]
DATA_DIR = REPO_ROOT / 'frontend' / 'data'
KNOWN_STATUSES = {code for code, _ in LICENSE_STATUSES}


class Command(BaseCommand):
    """Load agents and their state licences from the frontend's JSON.

        python manage.py seed_agents
        python manage.py seed_agents --agents path/agents.json --licenses path/agent-state-licenses.json

    Idempotent: an agent is matched by NPN and updated in place; a new NPN
    is created. Licence rows are matched by agent + state. Nothing is
    deleted. The licences file keys rows by the agents file's numeric `id`.
    """

    help = 'Create or update agents and their licences from agents.json and agent-state-licenses.json.'

    def add_arguments(self, parser):
        parser.add_argument('--agents', default=str(DATA_DIR / 'agents.json'), help='Path to agents.json.')
        parser.add_argument(
            '--licenses',
            default=str(DATA_DIR / 'agent-state-licenses.json'),
            help='Path to agent-state-licenses.json.',
        )

    def handle(self, *args, **options):
        agents_rows = self._load(options['agents'])
        license_rows = self._load(options['licenses'])
        states_by_code = {state.code: state for state in State.objects.all()}
        created = updated = licenses = 0

        with transaction.atomic():
            agents_by_json_id = {}
            for row in agents_rows:
                address = row.get('address')
                fields = {
                    'name': normalize_name(row['name']),
                    'aliases': normalize_aliases(row.get('aliases', [])),
                    'email': row.get('email', ''),
                    'phone': row.get('phone', ''),
                    'personal_email': row.get('personalEmail', ''),
                    'personal_phone': row.get('personalPhone', ''),
                    'is_active': row.get('status', 'active') != 'inactive',
                    **address_fields(address),
                }
                if address and address.get('state') and address['state'].upper() not in states_by_code:
                    raise CommandError(f"{row['name']}: unknown address state {address['state']}.")
                npn = str(row['npn']).strip()
                agent = Agent.objects.filter(npn=npn).first()
                if agent is None:
                    agent = Agent.objects.create(npn=npn, **fields)
                    created += 1
                else:
                    for field, value in fields.items():
                        setattr(agent, field, value)
                    agent.save()
                    updated += 1
                agents_by_json_id[str(row['id'])] = agent

            for row in license_rows:
                agent = agents_by_json_id.get(str(row['agentId']))
                if agent is None:
                    raise CommandError(f"Licence {row.get('id')}: no agent with id {row['agentId']} in the agents file.")
                code = row['state'].upper()
                if code not in states_by_code:
                    raise CommandError(f"Licence {row.get('id')}: unknown state code {code}.")
                status = row.get('status', 'active')
                if status not in KNOWN_STATUSES:
                    status = 'active'
                fields = {
                    'license_number': row.get('licenseNumber', ''),
                    'status': status,
                    'start_date': date.fromisoformat(row['startDate']) if row.get('startDate') else None,
                    'end_date': date.fromisoformat(row['endDate']) if row.get('endDate') else None,
                }
                AgentStateLicense.objects.update_or_create(
                    agent=agent, state=states_by_code[code], defaults=fields
                )
                licenses += 1

        self.stdout.write(
            self.style.SUCCESS(f'Agents: {created} created, {updated} updated; {licenses} licence rows written.')
        )

    def _load(self, path):
        path = Path(path)
        if not path.exists():
            raise CommandError(f'No such file: {path}')
        rows = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(rows, list):
            raise CommandError(f'{path}: expected a JSON array.')
        return rows
