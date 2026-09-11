"""The permission catalog - the living source of truth.

Every entry is (module, resource, action). The codename is always
``f'{resource.lower()}.{action}'``, which is what the rest of the code and the
frontend key off.

Adding a permission here is not enough on its own. Either

    python manage.py seed_permissions          # existing databases

or, for anything that ships, a data migration alongside it (see
roles/migrations/0002_seed_permissions.py) so fresh databases and CI get it
without a manual step. `test_catalog_matches_the_database` fails if catalog.py
and the migrations drift apart, so the reminder is automatic.
"""

USER_MANAGEMENT = 'User Management'
ROLE_MANAGEMENT = 'Role Management'

PERMISSIONS = [
    (USER_MANAGEMENT, 'User', 'create'),
    (USER_MANAGEMENT, 'User', 'update'),
    (USER_MANAGEMENT, 'User', 'detail'),
    (USER_MANAGEMENT, 'User', 'block'),
    (USER_MANAGEMENT, 'User', 'unblock'),
    (USER_MANAGEMENT, 'User', 'change_password'),
    (ROLE_MANAGEMENT, 'Role', 'create'),
    (ROLE_MANAGEMENT, 'Role', 'update'),
    (ROLE_MANAGEMENT, 'Role', 'detail'),
    (ROLE_MANAGEMENT, 'Role', 'delete'),
]


def codename_for(resource, action):
    return f'{resource.lower()}.{action}'


def sync(permission_model, prune=False):
    """Idempotently write `PERMISSIONS` into the database.

    Takes the model as an argument so a migration can hand in its historical
    version. Returns (created, updated, stale) codename lists.
    """
    created, updated = [], []

    for module, resource, action in PERMISSIONS:
        codename = codename_for(resource, action)
        obj, was_created = permission_model.objects.get_or_create(
            codename=codename,
            defaults={'module': module, 'resource': resource, 'action': action},
        )
        if was_created:
            created.append(codename)
        elif (obj.module, obj.resource, obj.action) != (module, resource, action):
            # A permission was re-filed under a different module or resource.
            obj.module, obj.resource, obj.action = module, resource, action
            obj.save(update_fields=['module', 'resource', 'action'])
            updated.append(codename)

    wanted = {codename_for(r, a) for _, r, a in PERMISSIONS}
    stale = sorted(
        permission_model.objects.exclude(codename__in=wanted).values_list(
            'codename', flat=True
        )
    )
    if prune and stale:
        permission_model.objects.filter(codename__in=stale).delete()

    return created, updated, stale
