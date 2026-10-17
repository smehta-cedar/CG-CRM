from django.db import migrations, models
from django.utils import timezone


def soft_delete_orphans(apps, schema_editor):
    # Before soft deletes cascaded, deleting a parent left its children live.
    # Mark those deleted too, repeating until a pass finds nothing (a contract's
    # notes only show up once the contract itself is marked).
    now = timezone.now()
    soft = [m for m in apps.get_models() if any(f.name == 'deleted_at' for f in m._meta.fields)]
    changed = True
    while changed:
        changed = False
        for model in soft:
            for field in model._meta.fields:
                if not field.is_relation or field.remote_field.on_delete is not models.CASCADE:
                    continue
                if field.related_model not in soft:
                    continue
                count = model._base_manager.filter(
                    deleted_at__isnull=True, **{f'{field.name}__deleted_at__isnull': False}
                ).update(deleted_at=now, updated_at=now)
                changed = changed or bool(count)


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0001_initial'),
        ('accounts', '0008_drop_agent_view'),
        ('agency', '0009_agencystatelicense_renewing'),
        ('agents', '0013_agentstatelicense_renewing'),
        ('carriers', '0009_carrierstatelicense_renewing_and_more'),
        ('contracts', '0006_agency_contract_status'),
        ('passwords', '0009_site_link_optional_credentials'),
        ('policies', '0007_carrier_policy_type_optional'),
        ('requests', '0004_tasks'),
        ('storefront', '0002_product_category_product_image_url_and_more'),
    ]

    operations = [
        migrations.RunPython(soft_delete_orphans, migrations.RunPython.noop),
    ]
