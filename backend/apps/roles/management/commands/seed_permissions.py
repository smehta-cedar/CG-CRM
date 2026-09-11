from django.core.management.base import BaseCommand

from apps.roles.catalog import PERMISSIONS, sync
from apps.roles.models import Permission


class Command(BaseCommand):
    help = 'Sync apps.roles.catalog.PERMISSIONS into the Permission table.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--prune',
            action='store_true',
            help='Also delete permissions that are no longer in the catalog. '
                 'This revokes them from every role that holds them.',
        )

    def handle(self, *args, **options):
        prune = options['prune']
        created, updated, stale = sync(Permission, prune=prune)

        for codename in created:
            self.stdout.write(self.style.SUCCESS(f'  + {codename}'))
        for codename in updated:
            self.stdout.write(f'  ~ {codename} (re-filed)')

        if stale:
            if prune:
                for codename in stale:
                    self.stdout.write(self.style.WARNING(f'  - {codename}'))
            else:
                self.stdout.write(self.style.WARNING(
                    f'{len(stale)} permission(s) in the database are not in the '
                    f'catalog: {", ".join(stale)}. Re-run with --prune to remove them.'
                ))

        self.stdout.write(
            f'Catalog: {len(PERMISSIONS)} permission(s); '
            f'{len(created)} created, {len(updated)} updated, {len(stale)} stale.'
        )
