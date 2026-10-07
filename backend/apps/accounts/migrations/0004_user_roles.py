import django.db.models.deletion
from django.db import migrations, models


def copy_role_to_roles(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    # _base_manager: soft-deleted users keep their role too.
    for user in User._base_manager.exclude(role=None):
        user.roles.add(user.role_id)


def copy_roles_to_role(apps, schema_editor):
    # Going back keeps one role per user: the first by name.
    User = apps.get_model('accounts', 'User')
    for user in User._base_manager.all():
        first = user.roles.order_by('name').first()
        if first is not None:
            user.role = first
            user.save(update_fields=['role'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_user_agent'),
    ]

    operations = [
        # Free the "users" reverse name for the new field while both exist.
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='+',
                to='accounts.role',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='roles',
            field=models.ManyToManyField(blank=True, related_name='users', to='accounts.role'),
        ),
        migrations.RunPython(copy_role_to_roles, copy_roles_to_role),
        migrations.RemoveField(
            model_name='user',
            name='role',
        ),
    ]
