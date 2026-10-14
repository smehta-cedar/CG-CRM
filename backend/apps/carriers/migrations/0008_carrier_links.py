from django.db import migrations, models


def copy_links(apps, schema_editor):
    """The carrier's own link becomes "Website", and each distinct portal link
    on its passwords becomes "Portal" ("Portal 2", … for more). Runs before the
    carrier's link and the passwords' link columns are dropped."""
    Carrier = apps.get_model('carriers', 'Carrier')
    Password = apps.get_model('passwords', 'Password')
    for carrier in Carrier._base_manager.all():
        links = []
        if carrier.link:
            links.append({'name': 'Website', 'url': carrier.link})
        urls = {link['url'] for link in links}
        portals = Password._base_manager.filter(carrier_id=carrier.pk, deleted_at__isnull=True).exclude(link='')
        for url in portals.order_by('created_at').values_list('link', flat=True):
            if url in urls:
                continue
            urls.add(url)
            count = sum(1 for link in links if link['name'].startswith('Portal'))
            links.append({'name': 'Portal' if count == 0 else f'Portal {count + 1}', 'url': url})
        if links:
            carrier.links = links
            carrier.save(update_fields=['links'])


class Migration(migrations.Migration):

    dependencies = [
        ('carriers', '0007_carrier_certification_lines'),
        ('passwords', '0005_move_agency_contract_logins'),
    ]

    operations = [
        migrations.AddField(
            model_name='carrier',
            name='links',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(copy_links, migrations.RunPython.noop),
        migrations.RemoveField(model_name='carrier', name='link'),
    ]
