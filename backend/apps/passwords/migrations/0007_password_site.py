import django.db.models.functions.text
from django.db import migrations, models


def copy_carrier_names(apps, schema_editor):
    """Each password's site starts as its carrier's name, deleted ones too."""
    Password = apps.get_model('passwords', 'Password')
    for password in Password._base_manager.select_related('carrier'):
        password.site = password.carrier.name.strip()
        password.save(update_fields=['site'])


class Migration(migrations.Migration):
    """Passwords are kept by site (free text) instead of by carrier."""

    dependencies = [
        ('passwords', '0006_remove_password_link'),
    ]

    operations = [
        migrations.AddField(
            model_name='password',
            name='site',
            field=models.CharField(default='', max_length=255),
            preserve_default=False,
        ),
        migrations.RunPython(copy_carrier_names, migrations.RunPython.noop),
        migrations.RemoveConstraint(model_name='password', name='uniq_password_agent_carrier_alive'),
        migrations.RemoveConstraint(model_name='password', name='uniq_password_agency_carrier_alive'),
        migrations.RemoveField(model_name='password', name='carrier'),
        migrations.AddConstraint(
            model_name='password',
            constraint=models.UniqueConstraint(
                models.F('agent'),
                django.db.models.functions.text.Lower('site'),
                condition=models.Q(('agent__isnull', False), ('deleted_at__isnull', True)),
                name='uniq_password_agent_site_alive',
                violation_error_message='This agent already has a password at this site.',
            ),
        ),
        migrations.AddConstraint(
            model_name='password',
            constraint=models.UniqueConstraint(
                models.F('agency'),
                django.db.models.functions.text.Lower('site'),
                condition=models.Q(('agency__isnull', False), ('deleted_at__isnull', True)),
                name='uniq_password_agency_site_alive',
                violation_error_message='The agency already has a password at this site.',
            ),
        ),
    ]
