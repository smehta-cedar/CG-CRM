import django.db.models.deletion
import django.db.models.functions.text
import uuid
from django.conf import settings
from django.db import migrations, models


def split_sites_from_carriers(apps, schema_editor):
    """Undo 0007. A password whose site names a carrier gets that carrier
    back; any other becomes a site password at a Site of that name, with its
    notes, and the carrier password row is removed. Deleted rows too."""
    Carrier = apps.get_model('carriers', 'Carrier')
    Password = apps.get_model('passwords', 'Password')
    PasswordNote = apps.get_model('passwords', 'PasswordNote')
    Site = apps.get_model('passwords', 'Site')
    SitePassword = apps.get_model('passwords', 'SitePassword')
    SitePasswordNote = apps.get_model('passwords', 'SitePasswordNote')
    carriers = Carrier._base_manager.all()

    for password in Password._base_manager.all():
        name = password.site.strip()
        carrier = (
            carriers.filter(name__iexact=name, deleted_at__isnull=True).first()
            or carriers.filter(name__iexact=name).first()
        )
        if carrier is not None:
            password.carrier = carrier
            password.save(update_fields=['carrier'])
            continue

        site = Site._base_manager.filter(name__iexact=name, deleted_at__isnull=True).first()
        if site is None:
            site = Site._base_manager.create(
                name=name, created_by_id=password.created_by_id, updated_by_id=password.created_by_id
            )
        moved = SitePassword._base_manager.create(
            agent_id=password.agent_id,
            agency_id=password.agency_id,
            site=site,
            username=password.username,
            portal_password=password.portal_password,
            status=password.status,
            deleted_at=password.deleted_at,
            deleted_by_id=password.deleted_by_id,
            created_by_id=password.created_by_id,
            updated_by_id=password.updated_by_id,
        )
        # auto_now_add / auto_now would stamp today; keep the original times.
        SitePassword._base_manager.filter(pk=moved.pk).update(
            created_at=password.created_at, updated_at=password.updated_at
        )
        for note in PasswordNote._base_manager.filter(password_id=password.pk):
            copied = SitePasswordNote._base_manager.create(
                password=moved,
                kind=note.kind,
                changes=note.changes,
                created_by_id=note.created_by_id,
                updated_by_id=note.updated_by_id,
            )
            SitePasswordNote._base_manager.filter(pk=copied.pk).update(created_at=note.created_at)
        # A plain queryset delete: the historical model has no soft delete.
        Password._base_manager.filter(pk=password.pk).delete()


class Migration(migrations.Migration):
    """Carrier passwords are back (0007 had turned carrier into a free-text
    site), and sites get their own tables: Site and SitePassword."""

    dependencies = [
        ('agency', '0007_license_statuses_expired'),
        ('agents', '0012_license_statuses_expired'),
        ('carriers', '0008_carrier_links'),
        ('passwords', '0007_password_site'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Site',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('priority', models.PositiveIntegerField(db_index=True, default=0)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, editable=False, null=True)),
                ('name', models.CharField(max_length=255)),
            ],
            options={
                'ordering': ('priority', '-created_at'),
                'get_latest_by': 'created_at',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='SitePassword',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('priority', models.PositiveIntegerField(db_index=True, default=0)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, editable=False, null=True)),
                ('username', models.CharField(max_length=255)),
                ('portal_password', models.CharField(max_length=255)),
                ('status', models.CharField(choices=[('active', 'Active'), ('pending', 'Pending'), ('inactive', 'Inactive')], default='active', max_length=10)),
            ],
            options={
                'ordering': ('priority', '-created_at'),
                'get_latest_by': 'created_at',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='SitePasswordNote',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('priority', models.PositiveIntegerField(db_index=True, default=0)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, editable=False, null=True)),
                ('kind', models.CharField(choices=[('added', 'Added'), ('edited', 'Edited')], max_length=10)),
                ('changes', models.JSONField(default=list)),
            ],
            options={
                'ordering': ('-created_at',),
                'get_latest_by': 'created_at',
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='site',
            name='created_by',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='site',
            name='deleted_by',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='site',
            name='updated_by',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='sitepassword',
            name='agency',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='site_passwords', to='agency.agency'),
        ),
        migrations.AddField(
            model_name='sitepassword',
            name='agent',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='site_passwords', to='agents.agent'),
        ),
        migrations.AddField(
            model_name='sitepassword',
            name='created_by',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='sitepassword',
            name='deleted_by',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='sitepassword',
            name='site',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='passwords', to='passwords.site'),
        ),
        migrations.AddField(
            model_name='sitepassword',
            name='updated_by',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='sitepasswordnote',
            name='created_by',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='sitepasswordnote',
            name='deleted_by',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='sitepasswordnote',
            name='password',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notes', to='passwords.sitepassword'),
        ),
        migrations.AddField(
            model_name='sitepasswordnote',
            name='updated_by',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddConstraint(
            model_name='site',
            constraint=models.UniqueConstraint(django.db.models.functions.text.Lower('name'), condition=models.Q(('deleted_at__isnull', True)), name='uniq_site_name_alive', violation_error_message='A site with this name already exists.'),
        ),
        migrations.AddConstraint(
            model_name='sitepassword',
            constraint=models.UniqueConstraint(condition=models.Q(('agent__isnull', False), ('deleted_at__isnull', True)), fields=('agent', 'site'), name='uniq_site_password_agent_alive', violation_error_message='This agent already has a password at this site.'),
        ),
        migrations.AddConstraint(
            model_name='sitepassword',
            constraint=models.UniqueConstraint(condition=models.Q(('agency__isnull', False), ('deleted_at__isnull', True)), fields=('agency', 'site'), name='uniq_site_password_agency_alive', violation_error_message='The agency already has a password at this site.'),
        ),
        migrations.AddConstraint(
            model_name='sitepassword',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('agency__isnull', True), ('agent__isnull', False)), models.Q(('agency__isnull', False), ('agent__isnull', True)), _connector='OR'), name='site_password_agent_or_agency', violation_error_message='A password belongs to an agent or the agency.'),
        ),
        migrations.AddField(
            model_name='password',
            name='carrier',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='passwords', to='carriers.carrier'),
        ),
        migrations.RunPython(split_sites_from_carriers, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name='password',
            name='uniq_password_agent_site_alive',
        ),
        migrations.RemoveConstraint(
            model_name='password',
            name='uniq_password_agency_site_alive',
        ),
        migrations.RemoveField(
            model_name='password',
            name='site',
        ),
        migrations.AlterField(
            model_name='password',
            name='carrier',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='passwords', to='carriers.carrier'),
        ),
        migrations.AddConstraint(
            model_name='password',
            constraint=models.UniqueConstraint(condition=models.Q(('deleted_at__isnull', True)), fields=('agent', 'carrier'), name='uniq_password_agent_carrier_alive', violation_error_message='This agent already has a password at this carrier.'),
        ),
        migrations.AddConstraint(
            model_name='password',
            constraint=models.UniqueConstraint(condition=models.Q(('agency__isnull', False), ('deleted_at__isnull', True)), fields=('agency', 'carrier'), name='uniq_password_agency_carrier_alive', violation_error_message='The agency already has a password at this carrier.'),
        ),
    ]
