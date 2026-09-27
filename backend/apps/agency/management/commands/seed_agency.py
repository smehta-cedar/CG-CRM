import json
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.agency.models import LICENSE_STATUSES, Agency, AgencyStateLicense, State
from apps.agency.utils import normalize_aliases, normalize_name

# backend/apps/agency/management/commands -> repo root
REPO_ROOT = Path(__file__).resolve().parents[5]
DATA_DIR = REPO_ROOT / 'frontend' / 'data'
KNOWN_STATUSES = {code for code, _ in LICENSE_STATUSES}


class Command(BaseCommand):
    """Load the agency and its state licences from the frontend's JSON.

        python manage.py seed_agency

    agency.json is one object (the agency is a singleton on the frontend);
    it is matched by name and updated in place, or created. Licence rows
    from agency-state-licenses.json are matched by state. Nothing is deleted.
    """

    help = 'Create or update the agency from agency.json and its licences from agency-state-licenses.json.'

    def add_arguments(self, parser):
        parser.add_argument('--agency', default=str(DATA_DIR / 'agency.json'))
        parser.add_argument('--licenses', default=str(DATA_DIR / 'agency-state-licenses.json'))

    def handle(self, *args, **options):
        agency_path = Path(options['agency'])
        licenses_path = Path(options['licenses'])
        for path in (agency_path, licenses_path):
            if not path.exists():
                raise CommandError(f'No such file: {path}')
        row = json.loads(agency_path.read_text(encoding='utf-8'))
        license_rows = json.loads(licenses_path.read_text(encoding='utf-8'))
        if not isinstance(row, dict) or not isinstance(license_rows, list):
            raise CommandError('Expected agency.json to be one object and the licences file a JSON array.')

        states_by_code = {state.code: state for state in State.objects.all()}
        with transaction.atomic():
            name = normalize_name(row['name'])
            fields = {
                'aliases': normalize_aliases(row.get('aliases', [])),
                'npn': str(row.get('npn', '')).strip(),
                'email': row.get('email', ''),
                'phone': row.get('phone', ''),
                'is_active': row.get('status', 'active') != 'inactive',
            }
            agency = Agency.objects.filter(name__iexact=name).first()
            if agency is None:
                agency = Agency.objects.create(name=name, **fields)
                verb = 'created'
            else:
                for field, value in fields.items():
                    setattr(agency, field, value)
                agency.save()
                verb = 'updated'

            for item in license_rows:
                code = item['state'].upper()
                if code not in states_by_code:
                    raise CommandError(f"Licence {item.get('id')}: unknown state code {code}.")
                status = item.get('status', 'active')
                AgencyStateLicense.objects.update_or_create(
                    agency=agency,
                    state=states_by_code[code],
                    defaults={
                        'license_number': item.get('licenseNumber', ''),
                        'status': status if status in KNOWN_STATUSES else 'active',
                        'start_date': date.fromisoformat(item['startDate']) if item.get('startDate') else None,
                        'end_date': date.fromisoformat(item['endDate']) if item.get('endDate') else None,
                    },
                )

        self.stdout.write(self.style.SUCCESS(f'Agency "{agency.name}" {verb}; {len(license_rows)} licence rows written.'))
