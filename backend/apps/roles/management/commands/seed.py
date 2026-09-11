import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.crypto import get_random_string

from apps.roles.catalog import sync
from apps.roles.models import Permission, Role

User = get_user_model()

SUPER_ADMIN_ROLE = 'Super Admin'

# Unambiguous alphabet: no O/0, l/1/I. A generated password gets read off a
# terminal and typed by hand at least once.
PASSWORD_ALPHABET = 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'


class Command(BaseCommand):
    """Bring a fresh environment up to a usable state.

    Idempotent throughout, so it is safe on an existing database: the catalog
    is synced, the Super Admin role is topped up with any permissions added
    since it was created, and an existing admin account is left alone rather
    than having its password reset out from under it.

    `seed_permissions` is the narrower command for routine deploys - it syncs
    the catalog and nothing else.
    """

    help = (
        'Seed the permission catalog, the Super Admin role, and the first '
        'admin user.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            default=os.environ.get('CRM_ADMIN_EMAIL'),
            help='Email for the first admin user. Or set CRM_ADMIN_EMAIL.',
        )
        parser.add_argument(
            '--name',
            default=os.environ.get('CRM_ADMIN_NAME', 'Super Admin'),
            help="Full name for the first admin user. Or set CRM_ADMIN_NAME.",
        )
        parser.add_argument(
            '--password',
            default=os.environ.get('CRM_ADMIN_PASSWORD'),
            help=(
                'Password for the first admin user. Or set CRM_ADMIN_PASSWORD. '
                'If omitted, one is generated, printed once, and the account '
                'is flagged to change it at first sign-in.'
            ),
        )
        parser.add_argument(
            '--skip-admin',
            action='store_true',
            help='Seed the catalog and the role, but create no user.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self._seed_catalog()
        role = self._seed_super_admin_role()

        if options['skip_admin']:
            self.stdout.write('Skipping the admin user (--skip-admin).')
            return

        if not options['email']:
            raise CommandError(
                'An admin email is required. Pass --email, set CRM_ADMIN_EMAIL, '
                'or pass --skip-admin.'
            )

        self._seed_admin_user(
            email=options['email'],
            full_name=options['name'],
            password=options['password'],
            role=role,
        )

    # ------------------------------------------------------------------
    def _seed_catalog(self):
        created, updated, stale = sync(Permission)
        self.stdout.write(
            f'Catalog: {Permission.objects.count()} permission(s) '
            f'({len(created)} created, {len(updated)} updated).'
        )
        if stale:
            self.stdout.write(self.style.WARNING(
                f'  {len(stale)} not in the catalog: {", ".join(stale)}. '
                f'Remove with: manage.py seed_permissions --prune'
            ))

    def _seed_super_admin_role(self):
        role, created = Role.objects.get_or_create(name=SUPER_ADMIN_ROLE)

        # Always reset to the full catalog rather than only filling it on
        # creation, so permissions added later reach this role too.
        before = set(role.permissions.values_list('codename', flat=True))
        role.permissions.set(Permission.objects.all())
        after = set(role.permissions.values_list('codename', flat=True))

        if created:
            self.stdout.write(self.style.SUCCESS(
                f"Role '{SUPER_ADMIN_ROLE}' created with {len(after)} permission(s)."
            ))
        elif after - before:
            self.stdout.write(
                f"Role '{SUPER_ADMIN_ROLE}' topped up with: "
                f"{', '.join(sorted(after - before))}."
            )
        else:
            self.stdout.write(f"Role '{SUPER_ADMIN_ROLE}' already up to date.")

        return role

    def _seed_admin_user(self, *, email, full_name, password, role):
        normalized = User.objects.normalize_email(email)
        existing = User.objects.filter(email__iexact=normalized).first()

        if existing is not None:
            # Never touch an existing account's password: re-running the
            # command must not be a way to silently take one over.
            changed = []
            if existing.role_id != role.id:
                existing.role = role
                changed.append('role')
            if not existing.is_staff:
                existing.is_staff = True
                changed.append('is_staff')
            if changed:
                existing.save(update_fields=changed)
                self.stdout.write(
                    f'Admin user {existing.email} already existed; '
                    f'updated {", ".join(changed)}.'
                )
            else:
                self.stdout.write(
                    f'Admin user {existing.email} already exists; left alone.'
                )
            return existing

        generated = password is None
        if generated:
            password = get_random_string(20, PASSWORD_ALPHABET)

        user = User.objects.create_user(
            email=normalized,
            password=password,
            full_name=full_name,
            role=role,
            is_staff=True,
            # Also a Django superuser, so this account can reach the Django
            # admin site and is not locked out if the role is ever misedited.
            # It carries the role as well, so the normal permission path is
            # exercised rather than only the superuser bypass.
            is_superuser=True,
            # A password nobody chose has been printed to a terminal and
            # probably a CI log. It is a handover credential, not a real one.
            must_change_password=generated,
        )

        self.stdout.write(self.style.SUCCESS(f'Admin user {user.email} created.'))
        if generated:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(f'  Password: {password}'))
            self.stdout.write(self.style.WARNING(
                '  Shown once. Must be changed at first sign-in.'
            ))
            self.stdout.write('')

        return user
