import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.agency.models import State
from apps.carriers.models import CARRIER_STATUSES, LINES_OF_BUSINESS, Carrier
from apps.carriers.utils import normalize_aliases, normalize_lines, normalize_name, sync_licenses

# backend/apps/carriers/management/commands -> repo root
REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_FILE = REPO_ROOT / 'frontend' / 'data' / 'carriers.json'


def license_row(state, row):
    """A state row for sync_licenses: `row`'s values when it exists, else a blank active one."""
    if row is None:
        return {
            'state': state,
            'license_number': '',
            'status': 'active',
            'start_date': None,
            'end_date': None,
            'life': False,
            'health': False,
        }
    fields = ('license_number', 'status', 'start_date', 'end_date', 'life', 'health')
    return {'state': state, **{field: getattr(row, field) for field in fields}}


class Command(BaseCommand):
    """Load carriers from the frontend's carriers.json.

        python manage.py seed_carriers
        python manage.py seed_carriers --file path/to/carriers.json

    Idempotent: a carrier is matched by name (ignoring case) and updated in
    place; a new name is created. Each listed state gets a blank active state
    row; a state row already there keeps its number, status, dates and lines.
    A carrier's state no longer listed loses its row. The JSON rows look like

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

                status = row.get('status', 'active')
                if status not in dict(CARRIER_STATUSES):
                    raise CommandError(f'{name}: unknown status {status}.')

                fields = {
                    'name': name,
                    'aliases': normalize_aliases(row.get('aliases', [])),
                    'lines_of_business': lines,
                    'status': status,
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
                kept = {row.state.code: row for row in carrier.licenses.all()}
                sync_licenses(carrier, None, [license_row(states_by_code[code], kept.get(code)) for code in codes])

        self.stdout.write(self.style.SUCCESS(f'Carriers: {created} created, {updated} updated from {path}.'))
