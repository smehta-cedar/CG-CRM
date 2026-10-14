import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.agents.models import Agent
from apps.passwords.models import PASSWORD_STATUSES, Site, SitePassword

# backend/apps/passwords/management/commands -> repo root
REPO_ROOT = Path(__file__).resolve().parents[5]
DATA_DIR = REPO_ROOT / 'frontend' / 'data'
KNOWN_STATUSES = {code for code, _ in PASSWORD_STATUSES}


class Command(BaseCommand):
    """Load sites and site passwords from the frontend's site-passwords.json.

        python manage.py seed_site_passwords

    Each row names its site; a missing site is created (matched whatever its
    case). Agents are looked up by the NPN their agents.json id maps to, so
    run seed_agents first. Idempotent: a password is matched by agent + site
    and updated in place. Nothing is deleted.
    """

    help = 'Create or update sites and site passwords from site-passwords.json (needs agents.json).'

    def add_arguments(self, parser):
        parser.add_argument('--site-passwords', default=str(DATA_DIR / 'site-passwords.json'))
        parser.add_argument('--agents', default=str(DATA_DIR / 'agents.json'))

    def handle(self, *args, **options):
        rows = self._load(options['site_passwords'])
        npn_by_json_id = {str(row['id']): str(row['npn']).strip() for row in self._load(options['agents'])}
        sites_created = created = updated = 0

        with transaction.atomic():
            for row in rows:
                npn = npn_by_json_id.get(str(row['agentId']))
                agent = Agent.objects.filter(npn=npn).first() if npn else None
                if agent is None:
                    raise CommandError(f"Site password {row.get('id')}: no agent for id {row['agentId']} (run seed_agents).")
                name = str(row.get('site', '')).strip()
                if not name:
                    raise CommandError(f"Site password {row.get('id')}: no site.")
                site = Site.objects.filter(name__iexact=name).first()
                if site is None:
                    site = Site.objects.create(name=name)
                    sites_created += 1
                status = row.get('status', 'active')
                fields = {
                    'username': row['username'],
                    'portal_password': row.get('portalPassword', ''),
                    'status': status if status in KNOWN_STATUSES else 'active',
                }
                _, was_created = SitePassword.objects.update_or_create(agent=agent, site=site, defaults=fields)
                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(
            self.style.SUCCESS(f'Sites: {sites_created} created. Site passwords: {created} created, {updated} updated.')
        )

    def _load(self, path):
        path = Path(path)
        if not path.exists():
            raise CommandError(f'No such file: {path}')
        rows = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(rows, list):
            raise CommandError(f'{path}: expected a JSON array.')
        return rows
