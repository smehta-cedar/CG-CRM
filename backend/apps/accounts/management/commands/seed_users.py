import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Role, RolePermission, User
from apps.accounts.models.roles import (
    ACTIONS,
    ADMIN_ROLE_NAME,
    AGENT_ROLE_NAME,
    OPERATIONS_ROLE_NAME,
    PERMISSION_LABELS,
)

# backend/apps/accounts/management/commands -> repo root
REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_FILE = REPO_ROOT / 'frontend' / 'data' / 'users.json'

# The roles users.json knows: Admin may do everything on every module,
# Operations ("staff" in older files) may view every module. Agent sign-ins
# use the separate Agent role (AGENT_ROLE_NAME), not a users.json row.
ROLE_NAMES = {'admin': ADMIN_ROLE_NAME, 'operations': OPERATIONS_ROLE_NAME}
ROLE_ALIASES = {'staff': 'operations'}


class Command(BaseCommand):
    """Load sign-in accounts from the frontend's users.json.

        python manage.py seed_users

    Gives the built-in Admin, Operations and Agent roles their default
    permissions when they have none yet; a role already set up on the Roles
    page is left alone. Then a user per row, matched by email and updated in
    place.
    Passwords are set exactly as the file holds them, skipping the strength
    validators, so keep this to local development. Existing superusers are
    never touched.
    """

    help = 'Set up the built-in roles if empty and load the users in users.json (local dev only).'

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
            self._ensure_agent_role()

            for row in rows:
                email = row['email'].strip().lower()
                key = row.get('role', 'operations')
                role = roles.get(ROLE_ALIASES.get(key, key), roles['operations'])
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

        self.stdout.write(
            self.style.SUCCESS(
                f'Users: {created} created, {updated} updated; roles {ADMIN_ROLE_NAME}, {OPERATIONS_ROLE_NAME} and {AGENT_ROLE_NAME} in place.'
            )
        )

    def _get_role(self, name):
        """The role and whether it still needs its defaults (it has no permission rows)."""
        role = Role.objects.filter(name__iexact=name).first() or Role.objects.create(name=name)
        return role, not role.permissions.exists()

    def _ensure_role(self, name, full):
        role, empty = self._get_role(name)
        if empty:
            for module in PERMISSION_LABELS:
                flags = {f'can_{action}': (full or action == 'view') for action in ACTIONS}
                RolePermission.objects.create(role=role, module=module, **flags)
        return role

    def _ensure_agent_role(self):
        """The role every agent OTP account uses: Calendar, to see and file their own requests."""
        role, empty = self._get_role(AGENT_ROLE_NAME)
        if empty:
            RolePermission.objects.create(role=role, module='requests', can_view=True, can_create=True)
        return role
