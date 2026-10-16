from django.db import migrations


class Migration(migrations.Migration):
    """The portal link moved to the carrier's named links (carriers 0008)."""

    dependencies = [
        ('passwords', '0005_move_agency_contract_logins'),
        ('carriers', '0008_carrier_links'),
    ]

    operations = [
        migrations.RemoveField(model_name='password', name='link'),
    ]
