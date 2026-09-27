import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.agency.models import State
from apps.carriers.models import LINES_OF_BUSINESS, Carrier
from apps.carriers.utils import normalize_aliases, normalize_lines, normalize_name

# backend/apps/carriers/management/commands -> repo root
REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_FILE = REPO_ROOT / 'frontend' / 'data' / 'carriers.json'


class Command(BaseCommand):
    """Load carriers from the frontend's carriers.json.

        python manage.py seed_carriers
        python manage.py seed_carriers --file path/to/carriers.json

    Idempotent: a carrier is matched by name (ignoring case) and updated in
    place; a new name is created. Nothing is deleted. The JSON rows look like

        {"name": "Humana", "aliases": [], "linesOfBusiness": ["MAPD"],
         "availableStates": ["FL", "TX"], "status": "active"}
    """

    help = "Create or update carriers from a carriers.json file (default: frontend/data/carriers.json)."

    def add_arguments(self, parser):
        parser.add_argument('--file', default=str(DEFAULT_FILE), help='Path to carriers.json.')

    def handle(self, *args, **options):
        path = Path(options['file'])
        if not path.exists():
            raise CommandError(f'No such file: {path}')
        rows = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(rows, list):
            raise CommandError('Expected a JSON array of carriers.')

        states_by_code = {state.code: state for state in State.objects.all()}
        created = updated = 0

        with transaction.atomic():
            for row in rows:
                name = normalize_name(row['name'])
                lines = normalize_lines(row.get('linesOfBusiness', []))
                unknown_lines = sorted(set(row.get('linesOfBusiness', [])) - set(LINES_OF_BUSINESS))
                if unknown_lines:
                    raise CommandError(f"{name}: unknown line of business {', '.join(unknown_lines)}.")
                codes = sorted({code.upper() for code in row.get('availableStates', [])})
                unknown_codes = sorted(set(codes) - set(states_by_code))
                if unknown_codes:
                    raise CommandError(f"{name}: unknown state code {', '.join(unknown_codes)}.")

                fields = {
                    'name': name,
                    'aliases': normalize_aliases(row.get('aliases', [])),
                    'lines_of_business': lines,
                    'is_active': row.get('status', 'active') != 'inactive',
                }
                carrier = Carrier.objects.filter(name__iexact=name).first()
                if carrier is None:
                    carrier = Carrier.objects.create(**fields)
                    created += 1
                else:
                    for field, value in fields.items():
                        setattr(carrier, field, value)
                    carrier.save()
                    updated += 1
                carrier.available_states.set(states_by_code[code] for code in codes)

        self.stdout.write(self.style.SUCCESS(f'Carriers: {created} created, {updated} updated from {path}.'))
