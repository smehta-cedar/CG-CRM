from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0003_agent_personal_dates_ssn'),
    ]

    operations = [
        migrations.AddField(
            model_name='agent',
            name='login_code',
            field=models.CharField(blank=True, default='', max_length=128),
        ),
    ]
