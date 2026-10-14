from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agency', '0005_alter_agencystatelicense_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='agencystatelicense',
            name='health',
            field=models.BooleanField(default=False, help_text='The licence covers health insurance.'),
        ),
        migrations.AddField(
            model_name='agencystatelicense',
            name='life',
            field=models.BooleanField(default=False, help_text='The licence covers life insurance.'),
        ),
    ]
