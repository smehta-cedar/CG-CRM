from django.db import migrations

# A frozen snapshot, deliberately not imported from apps.roles.catalog:
# a migration has to keep describing the state of the world at the moment it
# was written, and importing living code would make replaying history produce
# whatever today's catalog happens to say.
#
# Adding a permission later = add it to catalog.py AND add a new data
# migration like this one. `test_catalog_matches_the_database` fails if you
# only do the first half.
PERMISSIONS = [
    ('User Management', 'User', 'create'),
    ('User Management', 'User', 'update'),
    ('User Management', 'User', 'detail'),
    ('User Management', 'User', 'block'),
    ('User Management', 'User', 'unblock'),
    ('User Management', 'User', 'change_password'),
    ('Role Management', 'Role', 'create'),
    ('Role Management', 'Role', 'update'),
    ('Role Management', 'Role', 'detail'),
    ('Role Management', 'Role', 'delete'),
]


def seed(apps, schema_editor):
    Permission = apps.get_model('roles', 'Permission')
    for module, resource, action in PERMISSIONS:
        Permission.objects.update_or_create(
            codename=f'{resource.lower()}.{action}',
            defaults={'module': module, 'resource': resource, 'action': action},
        )


def unseed(apps, schema_editor):
    Permission = apps.get_model('roles', 'Permission')
    codenames = [f'{r.lower()}.{a}' for _, r, a in PERMISSIONS]
    Permission.objects.filter(codename__in=codenames).delete()


class Migration(migrations.Migration):
    dependencies = [('roles', '0001_initial')]
    operations = [migrations.RunPython(seed, unseed)]
