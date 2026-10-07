import json
import secrets
from datetime import date, datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Role, RolePermission, User
from apps.agency.models import State
from apps.agents.models import Agent
from apps.carriers.models import Carrier
from apps.requests.models import REQUEST_STATUSES, Request
from apps.storefront.models import Product

# backend/apps/requests/management/commands -> repo root
REPO_ROOT = Path(__file__).resolve().parents[5]
DATA_DIR = REPO_ROOT / 'frontend' / 'data'
KNOWN_STATUSES = {code for code, _ in REQUEST_STATUSES}

# The public shop has no sign-in, so the Next server files tee orders as this
# account. Its role may only file and read requests.
SHOP_EMAIL = 'shop@cedargrove.local'
SHOP_ROLE = 'Shop'
TYPE_MAP = {'licensing': 'licensing', 'contract': 'contract', 'dayOff': 'day_off', 'merch': 'merch'}


class Command(BaseCommand):
    """Load HR requests from the frontend's JSON and set up the shop's service account.

        python manage.py seed_requests
        python manage.py seed_requests --shop-password 'chosen-secret'

    requests.json keys rows by the numeric ids in agents.json and
    carriers.json, so those are read too (agents by NPN, carriers by name).
    Requests are matched by their `createdAt` timestamp and updated in
    place, so the command can be re-run. The shop account is created if
    missing, with a generated password printed once (or the one given);
    put it in frontend/.env.local as SHOP_API_EMAIL / SHOP_API_PASSWORD.
    """

    help = 'Create or update HR requests from requests.json and merch-requests.json, plus the shop service account.'

    def add_arguments(self, parser):
        parser.add_argument('--requests', default=str(DATA_DIR / 'requests.json'))
        parser.add_argument('--merch', default=str(DATA_DIR / 'merch-requests.json'))
        parser.add_argument('--agents', default=str(DATA_DIR / 'agents.json'))
        parser.add_argument('--carriers', default=str(DATA_DIR / 'carriers.json'))
        parser.add_argument('--shop-password', default=None, help="The shop account's password; generated when left out.")

    def handle(self, *args, **options):
        rows = self._load(options['requests']) + self._load(options['merch'], optional=True)
        npn_by_json_id = {str(row['id']): str(row['npn']).strip() for row in self._load(options['agents'])}
        name_by_json_id = {str(row['id']): row['name'] for row in self._load(options['carriers'])}
        states_by_code = {state.code: state for state in State.objects.all()}
        # Orders from the JSON were for the tee; link them when seed_storefront has run.
        tee = Product.objects.filter(name__iexact='Cedar Grove Tee').first()
        created = updated = 0

        with transaction.atomic():
            for row in rows:
                request_type = TYPE_MAP.get(row.get('type'))
                if request_type is None:
                    raise CommandError(f"Request {row.get('id')}: unknown type {row.get('type')!r}.")
                fields = {
                    'type': request_type,
                    'status': row.get('status') if row.get('status') in KNOWN_STATUSES else 'pending',
                    'note': row.get('note', ''),
                }
                if request_type == 'merch':
                    color = tee.color(row.get('color', '')) if tee else None
                    fields.update(
                        product=tee,
                        buyer_name=row['buyerName'],
                        email=row.get('email', ''),
                        phone=row.get('phone', ''),
                        address=row.get('address', ''),
                        size=row.get('size', ''),
                        color=color['label'] if color else row.get('color', ''),
                        quantity=int(row.get('quantity') or 1),
                    )
                else:
                    npn = npn_by_json_id.get(str(row['agentId']))
                    agent = Agent.objects.filter(npn=npn).first() if npn else None
                    if agent is None:
                        raise CommandError(f"Request {row.get('id')}: no agent for id {row['agentId']} (run seed_agents).")
                    fields['agent'] = agent
                    if request_type in ('licensing', 'contract'):
                        name = name_by_json_id.get(str(row['carrierId']))
                        carrier = Carrier.objects.filter(name__iexact=name).first() if name else None
                        if carrier is None:
                            raise CommandError(f"Request {row.get('id')}: no carrier for id {row['carrierId']}.")
                        code = row['state'].upper()
                        if code not in states_by_code:
                            raise CommandError(f"Request {row.get('id')}: unknown state {code}.")
                        fields.update(carrier=carrier, state=states_by_code[code])
                    else:
                        fields.update(
                            start_date=date.fromisoformat(row['startDate']),
                            end_date=date.fromisoformat(row['endDate']),
                        )

                filed_at = datetime.fromisoformat(row['createdAt'].replace('Z', '+00:00'))
                existing = Request.all_objects.filter(created_at=filed_at).first()
                if existing is None:
                    filed = Request.objects.create(**fields)
                    # auto_now_add wrote "now"; keep the time it was really filed.
                    Request.all_objects.filter(pk=filed.pk).update(created_at=filed_at)
                    created += 1
                else:
                    for field, value in fields.items():
                        setattr(existing, field, value)
                    existing.save()
                    updated += 1

            password_note = self._ensure_shop_account(options['shop_password'])

        self.stdout.write(self.style.SUCCESS(f'Requests: {created} created, {updated} updated.'))
        if password_note:
            self.stdout.write(self.style.WARNING(password_note))

    def _ensure_shop_account(self, password):
        role, _ = Role.objects.get_or_create(name=SHOP_ROLE)
        RolePermission.objects.update_or_create(
            role=role, module='requests', defaults={'can_view': True, 'can_create': True}
        )
        user = User.all_objects.filter(email=SHOP_EMAIL).first()
        if user is None:
            password = password or secrets.token_urlsafe(18)
            user = User.objects.create_user(email=SHOP_EMAIL, password=password, full_name='Shop')
            user.roles.add(role)
            return f'Shop account {SHOP_EMAIL} created. SHOP_API_PASSWORD={password}  (shown once)'
        if password:
            user.set_password(password)
            user.is_active = True
            user.save()
            user.roles.add(role)
            return f'Shop account {SHOP_EMAIL} password updated.'
        # Adds the shop role and leaves any others the account holds.
        user.roles.add(role)
        return None

    def _load(self, path, optional=False):
        path = Path(path)
        if not path.exists():
            if optional:
                return []
            raise CommandError(f'No such file: {path}')
        text = path.read_text(encoding='utf-8').strip()
        rows = json.loads(text) if text else []
        if not isinstance(rows, list):
            raise CommandError(f'{path}: expected a JSON array.')
        return rows
