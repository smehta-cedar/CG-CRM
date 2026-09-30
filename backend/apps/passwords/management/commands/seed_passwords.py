import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.agents.models import Agent
from apps.carriers.models import Carrier
from apps.passwords.models import PASSWORD_STATUSES, Password

# backend/apps/passwords/management/commands -> repo root
REPO_ROOT = Path(__file__).resolve().parents[5]
DATA_DIR = REPO_ROOT / 'frontend' / 'data'
KNOWN_STATUSES = {code for code, _ in PASSWORD_STATUSES}


class Command(BaseCommand):
    """Load passwords from the frontend's passwords.json.

        python manage.py seed_passwords

    passwords.json keys rows by the numeric ids in agents.json and
    carriers.json, so all three files are read: an agent is looked up by the
    NPN its numeric id maps to, a carrier by the name. Run seed_agents and
    seed_carriers first. Idempotent: a password is matched by agent +
    carrier and updated in place. Nothing is deleted.
    """

    help = 'Create or update passwords from passwords.json (needs agents.json and carriers.json).'

    def add_arguments(self, parser):
        parser.add_argument('--passwords', default=str(DATA_DIR / 'passwords.json'))
        parser.add_argument('--agents', default=str(DATA_DIR / 'agents.json'))
        parser.add_argument('--carriers', default=str(DATA_DIR / 'carriers.json'))

    def handle(self, *args, **options):
        rows = self._load(options['passwords'])
        npn_by_json_id = {str(row['id']): str(row['npn']).strip() for row in self._load(options['agents'])}
        name_by_json_id = {str(row['id']): row['name'] for row in self._load(options['carriers'])}
        created = updated = 0

        with transaction.atomic():
            for row in rows:
                npn = npn_by_json_id.get(str(row['agentId']))
                agent = Agent.objects.filter(npn=npn).first() if npn else None
                if agent is None:
                    raise CommandError(f"Password {row.get('id')}: no agent for id {row['agentId']} (run seed_agents).")
                name = name_by_json_id.get(str(row['carrierId']))
                carrier = Carrier.objects.filter(name__iexact=name).first() if name else None
                if carrier is None:
                    raise CommandError(f"Password {row.get('id')}: no carrier for id {row['carrierId']} (run seed_carriers).")
                status = row.get('status', 'active')
                fields = {
                    'username': row['username'],
                    'portal_password': row.get('portalPassword', ''),
                    'link': row.get('link', ''),
                    'status': status if status in KNOWN_STATUSES else 'active',
                }
                _, was_created = Password.objects.update_or_create(agent=agent, carrier=carrier, defaults=fields)
                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(f'Passwords: {created} created, {updated} updated.'))

    def _load(self, path):
        path = Path(path)
        if not path.exists():
            raise CommandError(f'No such file: {path}')
        rows = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(rows, list):
            raise CommandError(f'{path}: expected a JSON array.')
        return rows
