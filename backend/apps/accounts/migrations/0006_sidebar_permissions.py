from django.db import migrations

# Permissions now follow the sidebar links. A snapshot of the codes: a
# migration must not change when the code does.
#
# Each old code's flags carry over to every link that replaces it.
SPLITS = {
    'agents': ('agents.list', 'agents.profile'),
    'carriers': ('carriers.list', 'carriers.profile'),
    'contracts': ('contracts.by_state', 'contracts.by_carriers'),
    'storefront': ('storefront.products',),
    # Rulebook was shown by the Overview's code.
    'dashboard': ('dashboard', 'rulebook'),
}
# No longer granted on their own: certifications go with Agents, agency
# contracts with Agency, policy types with Carriers or Agency.
DROPPED = ('certifications', 'agency_contracts', 'policy_types')
ACTIONS = ('view', 'create', 'update', 'delete')
AGENT_ROLE_NAME = 'Agent'


def to_sidebar_links(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    RolePermission = apps.get_model('accounts', 'RolePermission')
    roles = Role._base_manager.filter(deleted_at__isnull=True)
    rows = RolePermission._base_manager.filter(deleted_at__isnull=True, role__in=roles)

    for old, codes in SPLITS.items():
        for row in rows.filter(module=old):
            flags = {f'can_{action}': getattr(row, f'can_{action}') for action in ACTIONS}
            for code in codes:
                if code != old:
                    RolePermission._base_manager.update_or_create(
                        role_id=row.role_id, module=code, deleted_at__isnull=True, defaults=flags
                    )
            if old not in codes:
                row.delete()

    rows.filter(module__in=DROPPED).delete()

    # The Shop was open to every staff user, and ordering needed Requests' create.
    for role in roles.exclude(name__iexact=AGENT_ROLE_NAME):
        can_order = rows.filter(role=role, module='requests', can_create=True).exists()
        RolePermission._base_manager.update_or_create(
            role=role,
            module='storefront.shop',
            deleted_at__isnull=True,
            defaults={'can_view': True, 'can_create': can_order},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_system_roles'),
    ]

    operations = [
        migrations.RunPython(to_sidebar_links, migrations.RunPython.noop),
    ]
