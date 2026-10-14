from django.db import migrations

# A snapshot of SYSTEM_ROLE_NAMES: a migration must not change when the code does.
SYSTEM_ROLE_NAMES = ('Admin', 'Operations', 'Agent')


def ensure_system_roles(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    alive = Role._base_manager.filter(deleted_at__isnull=True)

    # Staff becomes Operations, keeping its users and permissions.
    if not alive.filter(name__iexact='Operations').exists():
        alive.filter(name__iexact='Staff').update(name='Operations')

    # New ones start with no permissions; they are set on the Roles page.
    for name in SYSTEM_ROLE_NAMES:
        role = alive.filter(name__iexact=name).first()
        if role is None:
            Role.objects.create(name=name)
        else:
            role.name = name
            role.is_active = True
            role.save(update_fields=['name', 'is_active'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_user_roles'),
    ]

    operations = [
        migrations.RunPython(ensure_system_roles, migrations.RunPython.noop),
    ]
