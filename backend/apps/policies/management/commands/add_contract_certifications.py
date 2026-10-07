import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.contracts.models import CarrierContract
from apps.policies.models import Certification
from apps.policies.utils import add_contract_certifications, certification_due_date


class Command(BaseCommand):
    help = (
        "Give every contracted agent a certification per line of business of each carrier they are "
        "contracted with, due on the next deadline (or --due). Safe to run again: lines already "
        "covered for that deadline are skipped. Run it after each deadline to start the next year."
    )

    def add_arguments(self, parser):
        parser.add_argument('--due', help='The deadline as YYYY-MM-DD. Defaults to the next one.')

    def handle(self, *args, **options):
        if options['due']:
            try:
                due_date = datetime.date.fromisoformat(options['due'])
            except ValueError:
                raise CommandError('--due must be YYYY-MM-DD.')
        else:
            due_date = certification_due_date()

        with transaction.atomic():
            touched = 0
            for contract in CarrierContract.objects.select_related('agent', 'carrier'):
                touched += len(add_contract_certifications(contract.agent, contract.carrier, due_date=due_date))
            # Rows from before due dates existed that no contract filled in go on this deadline too.
            dated = Certification.objects.filter(due_date__isnull=True).update(due_date=due_date)

        self.stdout.write(
            self.style.SUCCESS(
                f'{touched} certification(s) added or filled in for {due_date.isoformat()}; '
                f'{dated} other undated row(s) given that due date.'
            )
        )
