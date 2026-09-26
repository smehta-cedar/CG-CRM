from django.db import models
from django.db.models.functions import Lower, Upper

from apps.base.models import BaseModel

# Seeded by migration 0002_seed_states; the list there is a frozen copy.
US_STATES = (
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


def normalize_search_key(value):
    """"California, CA ,calif,ca" -> "california,ca,calif": trimmed,
    lowercased, blanks dropped, duplicates removed, order kept."""
    seen = set()
    terms = []
    for term in value.split(','):
        term = ' '.join(term.split()).lower()
        if term and term not in seen:
            seen.add(term)
            terms.append(term)
    return ','.join(terms)


class State(BaseModel):
    """A US state, e.g. "California" / "CA"."""

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=2, help_text='Two-letter USPS code, stored uppercase.')
    # Comma-separated terms a search may match, e.g. "california,ca,calif".
    search_key = models.CharField(max_length=255, blank=True)

    class Meta(BaseModel.Meta):
        ordering = ('name',)
        constraints = [
            models.UniqueConstraint(
                Lower('name'),
                condition=models.Q(deleted_at__isnull=True),
                name='uniq_state_name_alive',
                violation_error_message='A state with this name already exists.',
            ),
            models.UniqueConstraint(
                Upper('code'),
                condition=models.Q(deleted_at__isnull=True),
                name='uniq_state_code_alive',
                violation_error_message='A state with this code already exists.',
            ),
        ]

    def __str__(self):
        return f'{self.name} ({self.code})'

    @property
    def search_terms(self):
        return self.search_key.split(',') if self.search_key else []

    def save(self, *args, **kwargs):
        self.name = ' '.join(self.name.split())
        self.code = self.code.strip().upper()
        self.search_key = normalize_search_key(self.search_key)
        super().save(*args, **kwargs)
