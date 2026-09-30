from django.db import migrations

OLD, NEW = 'Supp/Ancillary', 'Ancillary'


def rename(old, new):
    def run(apps, schema_editor):
        # Renamed in place: the line keeps its slot, which stays in catalog order.
        Carrier = apps.get_model('carriers', 'Carrier')
        for carrier in Carrier._base_manager.filter(lines_of_business__icontains=old):
            lines = [new if line == old else line for line in carrier.lines_of_business]
            if lines != carrier.lines_of_business:
                carrier.lines_of_business = lines
                carrier.save(update_fields=['lines_of_business'])

    return run


rename_forward = rename(OLD, NEW)


class Migration(migrations.Migration):

    dependencies = [
        ('carriers', '0004_drop_general_line'),
    ]

    operations = [
        migrations.RunPython(rename_forward, rename(NEW, OLD)),
    ]
