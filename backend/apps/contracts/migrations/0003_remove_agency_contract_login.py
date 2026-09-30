from django.db import migrations


class Migration(migrations.Migration):
    """The agency's login moved to agency passwords (passwords 0005 copies it)."""

    dependencies = [
        ('contracts', '0002_agency_contracts'),
        ('passwords', '0005_move_agency_contract_logins'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='agencycarriercontract',
            name='username',
        ),
        migrations.RemoveField(
            model_name='agencycarriercontract',
            name='password',
        ),
    ]
