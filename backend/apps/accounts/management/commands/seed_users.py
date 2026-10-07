import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Role, RolePermission, User
from apps.accounts.models.roles import ACTIONS, PERMISSION_LABELS

# backend/apps/accounts/management/commands -> repo root
REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_FILE = REPO_ROOT / 'frontend' / 'data' / 'users.json'

# The two roles users.json knows: Admin may do everything on every module,
# Staff may view every module.
ROLE_NAMES = {'admin': 'Admin', 'staff': 'Staff'}


class Command(BaseCommand):
    """Load sign-in accounts from the frontend's users.json.

        python manage.py seed_users

    Creates the Admin and Staff roles (with permissions on every module) if
    missing, then a user per row, matched by email and updated in place.
    Passwords are set exactly as the file holds them, skipping the strength
    validators, so keep this to local development. Existing superusers are
    never touched.
    """

    help = 'Create or update the Admin / Staff roles and the users in users.json (local dev only).'

    def add_arguments(self, parser):
        parser.add_argument('--file', default=str(DEFAULT_FILE), help='Path to users.json.')

    def handle(self, *args, **options):
        path = Path(options['file'])
        if not path.exists():
            raise CommandError(f'No such file: {path}')
        rows = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(rows, list):
            raise CommandError('Expected a JSON array of users.')

        created = updated = 0
        with transaction.atomic():
            roles = {key: self._ensure_role(name, full=(key == 'admin')) for key, name in ROLE_NAMES.items()}

            for row in rows:
                email = row['email'].strip().lower()
                role = roles.get(row.get('role', 'staff'), roles['staff'])
                fields = {
                    'full_name': ' '.join(row['name'].split()),
                    'is_active': row.get('status', 'active') != 'inactive',
                }
                user = User.all_objects.filter(email=email).first()
                if user is None:
                    user = User.objects.create_user(email=email, password=row.get('password') or None, **fields)
                    created += 1
                else:
                    if user.is_superuser:
                        continue
                    for field, value in fields.items():
                        setattr(user, field, value)
                    if row.get('password'):
                        user.set_password(row['password'])
                    user.save()
                    updated += 1
                # The file gives one role; it replaces whatever roles the user had.
                user.roles.set([role])

        self.stdout.write(self.style.SUCCESS(f'Users: {created} created, {updated} updated; roles Admin and Staff in place.'))

    def _ensure_role(self, name, full):
        role, _ = Role.objects.get_or_create(name=name)
        for module in PERMISSION_LABELS:
            flags = {f'can_{action}': (full or action == 'view') for action in ACTIONS}
            RolePermission.objects.update_or_create(role=role, module=module, defaults=flags)
        return role
