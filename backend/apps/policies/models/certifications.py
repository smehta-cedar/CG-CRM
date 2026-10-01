import uuid

from django.db import models

from apps.agents.models import Agent
from apps.base.models import BaseModel
from apps.base.storage import PrivateStorage
from apps.carriers.models import Carrier


def certification_file_path(certification, filename):
    """A random name under certifications/; the name the user uploaded is
    kept in `file_name`."""
    return f'certifications/{uuid.uuid4().hex}.pdf'


class Certification(BaseModel):
    """One agent's yearly certification with a carrier for one of its lines
    of business, e.g. Maria Alva - Humana - MAPD, due 2027-09-15. Policy
    types play no part.

    `carrier` and `line_of_business` (one of LINES_OF_BUSINESS, the
    certification's sub type) are blank on rows made before they existed.
    `due_date` is the cycle's deadline, on settings.CERTIFICATION_DUE_MONTH
    / _DAY. Nothing here is required or checked: a certification is an
    add-on and nothing blocks on it, and the same row may appear twice.

    `start_date` and `end_date` are optional. `is_active` (from BaseModel)
    is the certification's status; it starts on.

    `file` is an optional PDF kept in private storage (never served by URL;
    GET /certifications/{id}/file/ hands it out), and `file_name` is the
    name it was uploaded with. A new upload replaces the old file.
    `is_verified` is set by hand; uploading a file does not set it.
    """

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='certifications')
    carrier = models.ForeignKey(
        Carrier, on_delete=models.CASCADE, related_name='certifications', null=True, blank=True
    )
    line_of_business = models.CharField(max_length=50, blank=True)
    due_date = models.DateField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    file = models.FileField(storage=PrivateStorage(), upload_to=certification_file_path, blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        parts = [self.agent, self.carrier, self.line_of_business]
        return ' - '.join(str(part) for part in parts if part)
