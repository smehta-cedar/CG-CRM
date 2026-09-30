from django.db import migrations


def strip_general(apps, schema_editor):
    # "General" is no longer a line of business. Carriers left with no lines
    # stay as they are; the form asks for one on their next save.
    Carrier = apps.get_model('carriers', 'Carrier')
    for carrier in Carrier._base_manager.filter(lines_of_business__icontains='General'):
        lines = [line for line in carrier.lines_of_business if line != 'General']
        if lines != carrier.lines_of_business:
            carrier.lines_of_business = lines
            carrier.save(update_fields=['lines_of_business'])


class Migration(migrations.Migration):

    dependencies = [
        ('carriers', '0003_carrier_status'),
    ]

    operations = [
        # Not reversible in data: which carriers were General isn't kept.
        migrations.RunPython(strip_general, migrations.RunPython.noop),
    ]
