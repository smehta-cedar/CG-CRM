from django.db import migrations, models


def flag_to_scope(apps, schema_editor):
    # Today's flag has no carriers behind it, so a required type becomes
    # "single". The historical model's plain manager includes deleted rows.
    PolicyType = apps.get_model('policies', 'PolicyType')
    PolicyType.objects.filter(certification_required=True).update(certification_scope='single')


def scope_to_flag(apps, schema_editor):
    PolicyType = apps.get_model('policies', 'PolicyType')
    PolicyType.objects.exclude(certification_scope='none').update(certification_required=True)


class Migration(migrations.Migration):

    dependencies = [
        ('carriers', '0001_initial'),
        ('policies', '0004_certification_file'),
    ]

    operations = [
        migrations.AddField(
            model_name='policytype',
            name='certification_scope',
            field=models.CharField(choices=[('none', 'None'), ('single', 'Single'), ('per_carrier', 'Per carrier')], default='none', max_length=20),
        ),
        migrations.RunPython(flag_to_scope, scope_to_flag),
        migrations.RemoveField(
            model_name='policytype',
            name='certification_required',
        ),
        migrations.AddField(
            model_name='policytype',
            name='certification_carriers',
            field=models.ManyToManyField(blank=True, related_name='certification_policy_types', to='carriers.carrier'),
        ),
        migrations.AddField(
            model_name='certification',
            name='carriers',
            field=models.ManyToManyField(blank=True, related_name='certifications', to='carriers.carrier'),
        ),
    ]
