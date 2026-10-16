from django.core.management.base import BaseCommand
from django.db import transaction

from apps.contracts.models import AgencyCarrierContract, CarrierContract
from apps.passwords.utils import add_pending_password


class Command(BaseCommand):
    """Give every live contract's agent (and the agency, for its own
    contracts) a pending password at that carrier when they have none.

        python manage.py add_pending_passwords

    New contracts get one as they are added (the contract APIs call the same
    helper); this fills in contracts from before that. Safe to rerun: a pair
    that already has a live password is skipped.
    """

    help = 'Add a pending password for every live agent and agency contract that has no password yet.'

    def handle(self, *args, **options):
        agent_added = agency_added = 0
        with transaction.atomic():
            for contract in CarrierContract.objects.select_related('agent', 'carrier'):
                if add_pending_password(contract.carrier, agent=contract.agent):
                    agent_added += 1
            for contract in AgencyCarrierContract.objects.select_related('agency', 'carrier'):
                if add_pending_password(contract.carrier, agency=contract.agency):
                    agency_added += 1
        self.stdout.write(
            self.style.SUCCESS(f'Pending passwords added: {agent_added} for agents, {agency_added} for the agency.')
        )
