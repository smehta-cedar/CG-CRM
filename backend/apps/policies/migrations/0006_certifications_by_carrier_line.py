import django.db.models.deletion
from django.db import migrations, models


def carriers_to_carrier(apps, schema_editor):
    # A row that covered several carriers becomes one row per carrier; the
    # copies share its dates, flags and file. The historical model's plain
    # manager includes deleted rows.
    Certification = apps.get_model('policies', 'Certification')
    for certification in Certification.objects.all():
        carriers = list(certification.carriers.all())
        if not carriers:
            continue
        certification.carrier = carriers[0]
        certification.save(update_fields=['carrier'])
        for carrier in carriers[1:]:
            certification.pk = None
            certification.carrier = carrier
            certification.save()


class Migration(migrations.Migration):
    """Certifications move off policy types onto a carrier and one of its
    lines of business, with a yearly due date."""

    dependencies = [
        ('carriers', '0006_carrier_state_licenses'),
        ('policies', '0005_certification_scope'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='certification',
            name='uniq_certification_pair_alive',
        ),
        # related_name '+' until the old carriers field (which holds
        # "certifications") is gone.
        migrations.AddField(
            model_name='certification',
            name='carrier',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='carriers.carrier'),
        ),
        migrations.RunPython(carriers_to_carrier, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='certification',
            name='carriers',
        ),
        migrations.AlterField(
            model_name='certification',
            name='carrier',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='certifications', to='carriers.carrier'),
        ),
        migrations.RemoveField(
            model_name='certification',
            name='policy_type',
        ),
        migrations.RemoveField(
            model_name='policytype',
            name='certification_carriers',
        ),
        migrations.RemoveField(
            model_name='policytype',
            name='certification_scope',
        ),
        migrations.AddField(
            model_name='certification',
            name='due_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='certification',
            name='line_of_business',
            field=models.CharField(blank=True, max_length=50),
        ),
    ]
