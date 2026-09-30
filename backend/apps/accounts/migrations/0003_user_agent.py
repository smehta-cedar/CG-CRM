import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_usernote'),
        ('agents', '0004_agent_login_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='agent',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='user',
                to='agents.agent',
            ),
        ),
    ]
