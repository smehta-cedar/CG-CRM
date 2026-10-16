from django.db import migrations

# Agents now sign in with the Agent role's sidebar permissions, like staff.
# Those rows were never read for agents, and copies of other roles may have
# left them on, so they start off. Calendar takes over from the agent's own
# requests section. A snapshot: a migration must not change when the code does.
AGENT_ROLE_NAME = 'Agent'
FLAGS = ('can_view', 'can_create', 'can_update', 'can_delete')


def reset_agent_role(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    RolePermission = apps.get_model('accounts', 'RolePermission')
    role = Role._base_manager.filter(deleted_at__isnull=True, name__iexact=AGENT_ROLE_NAME).first()
    if role is None:
        return
    rows = RolePermission._base_manager.filter(deleted_at__isnull=True, role=role)
    rows.exclude(module__startswith='agent_view.').update(**dict.fromkeys(FLAGS, False))
    requests = rows.filter(module='agent_view.requests').first()
    if requests is not None:
        RolePermission._base_manager.update_or_create(
            role=role,
            module='requests',
            deleted_at__isnull=True,
            defaults={flag: getattr(requests, flag) for flag in FLAGS},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_sidebar_permissions'),
    ]

    operations = [
        migrations.RunPython(reset_agent_role, migrations.RunPython.noop),
    ]
