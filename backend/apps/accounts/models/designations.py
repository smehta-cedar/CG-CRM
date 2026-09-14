from django.db import models
from django.db.models.functions import Lower

from apps.base.models import BaseModel


class Designation(BaseModel):
    """A job title, e.g. "Operations Manager". Separate from Role: the title
    is what someone is called, the role is what they may do."""

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta(BaseModel.Meta):
        constraints = [
            # Case-insensitive, and a deleted designation's name can be reused.
            models.UniqueConstraint(
                Lower('name'),
                condition=models.Q(deleted_at__isnull=True),
                name='uniq_designation_name_alive',
                violation_error_message='A designation with this name already exists.',
            ),
        ]

    def __str__(self):
        return self.name
