from django.db import migrations, models


def copy_lines(apps, schema_editor):
    """Every line a carrier already writes needs a certification, which is
    what appointing an agent did before this field existed."""
    Carrier = apps.get_model('carriers', 'Carrier')
    for carrier in Carrier._base_manager.all():
        carrier.certification_lines = list(carrier.lines_of_business)
        carrier.save(update_fields=['certification_lines'])


class Migration(migrations.Migration):

    dependencies = [
        ('carriers', '0006_carrier_state_licenses'),
    ]

    operations = [
        migrations.AddField(
            model_name='carrier',
            name='certification_lines',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(copy_lines, migrations.RunPython.noop),
    ]
