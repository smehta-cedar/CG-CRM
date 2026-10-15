from django.db import migrations


def drop_agent_view(apps, schema_editor):
    # Agents now use the sidebar permissions; the old portal's codes are gone.
    RolePermission = apps.get_model('accounts', 'RolePermission')
    RolePermission._base_manager.filter(module__startswith='agent_view.').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_agent_role_sidebar'),
    ]

    operations = [
        migrations.RunPython(drop_agent_view, migrations.RunPython.noop),
    ]
