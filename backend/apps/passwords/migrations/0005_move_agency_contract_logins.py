from django.db import migrations


def copy_logins(apps, schema_editor):
    """Each live agency contract's login becomes the agency's password at that
    carrier, unless the agency already has one there. Runs before the
    contract's username and password columns are dropped."""
    AgencyCarrierContract = apps.get_model('contracts', 'AgencyCarrierContract')
    Password = apps.get_model('passwords', 'Password')
    contracts = AgencyCarrierContract.objects.filter(deleted_at__isnull=True).exclude(username='')
    for contract in contracts:
        taken = Password.objects.filter(
            agency_id=contract.agency_id, carrier_id=contract.carrier_id, deleted_at__isnull=True
        ).exists()
        if taken:
            continue
        Password.objects.create(
            agency_id=contract.agency_id,
            carrier_id=contract.carrier_id,
            username=contract.username,
            portal_password=contract.password,
            status='active' if contract.is_active else 'inactive',
            created_by_id=contract.created_by_id,
            updated_by_id=contract.updated_by_id,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('passwords', '0004_password_agency'),
        ('contracts', '0002_agency_contracts'),
    ]

    operations = [
        migrations.RunPython(copy_logins, migrations.RunPython.noop),
    ]
