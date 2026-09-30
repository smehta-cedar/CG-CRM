from django.db import migrations, models


def clear_hashed_codes(apps, schema_editor):
    # Codes used to be Django hashes ("pbkdf2_sha256$..."). A hash can't be
    # turned back into the code, so those agents need a new code typed on the
    # agent form.
    Agent = apps.get_model('agents', 'Agent')
    Agent._base_manager.filter(login_code__contains='$').update(login_code='')


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0004_agent_login_code'),
    ]

    operations = [
        migrations.RunPython(clear_hashed_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='agent',
            name='login_code',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
    ]
