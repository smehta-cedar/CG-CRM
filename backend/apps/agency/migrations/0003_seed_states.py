from django.db import migrations

# Frozen copy of apps.agency.models.states.US_STATES at the time this
# migration was written. Do not import the live list here: a migration has to
# keep describing the world as it was.
STATES = (
    ('AL', 'Alabama'),
    ('AK', 'Alaska'),
    ('AZ', 'Arizona'),
    ('AR', 'Arkansas'),
    ('CA', 'California'),
    ('CO', 'Colorado'),
    ('CT', 'Connecticut'),
    ('DE', 'Delaware'),
    ('DC', 'District of Columbia'),
    ('FL', 'Florida'),
    ('GA', 'Georgia'),
    ('HI', 'Hawaii'),
    ('ID', 'Idaho'),
    ('IL', 'Illinois'),
    ('IN', 'Indiana'),
    ('IA', 'Iowa'),
    ('KS', 'Kansas'),
    ('KY', 'Kentucky'),
    ('LA', 'Louisiana'),
    ('ME', 'Maine'),
    ('MD', 'Maryland'),
    ('MA', 'Massachusetts'),
    ('MI', 'Michigan'),
    ('MN', 'Minnesota'),
    ('MS', 'Mississippi'),
    ('MO', 'Missouri'),
    ('MT', 'Montana'),
    ('NE', 'Nebraska'),
    ('NV', 'Nevada'),
    ('NH', 'New Hampshire'),
    ('NJ', 'New Jersey'),
    ('NM', 'New Mexico'),
    ('NY', 'New York'),
    ('NC', 'North Carolina'),
    ('ND', 'North Dakota'),
    ('OH', 'Ohio'),
    ('OK', 'Oklahoma'),
    ('OR', 'Oregon'),
    ('PA', 'Pennsylvania'),
    ('RI', 'Rhode Island'),
    ('SC', 'South Carolina'),
    ('SD', 'South Dakota'),
    ('TN', 'Tennessee'),
    ('TX', 'Texas'),
    ('UT', 'Utah'),
    ('VT', 'Vermont'),
    ('VA', 'Virginia'),
    ('WA', 'Washington'),
    ('WV', 'West Virginia'),
    ('WI', 'Wisconsin'),
    ('WY', 'Wyoming'),
)


def seed_states(apps, schema_editor):
    State = apps.get_model('agency', 'State')
    existing = set(State.objects.values_list('code', flat=True))
    State.objects.bulk_create([
        State(
            code=code,
            name=name,
            search_key=f'{name.lower()},{code.lower()}',
        )
        for code, name in STATES
        if code not in existing
    ])


def unseed_states(apps, schema_editor):
    State = apps.get_model('agency', 'State')
    State.objects.filter(code__in=[code for code, _ in STATES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('agency', '0002_state'),
    ]

    operations = [
        migrations.RunPython(seed_states, unseed_states),
    ]
