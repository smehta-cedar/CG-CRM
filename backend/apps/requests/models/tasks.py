from django.db import models
from django.utils import timezone

from apps.agency.models import State
from apps.agents.models import Agent
from apps.base.models import BaseModel
from apps.carriers.models import Carrier

from .requests import REQUEST_TYPES

# Same types as an agent's request; merch is the shop's alone.
TASK_TYPES = tuple((code, label) for code, label in REQUEST_TYPES if code != 'merch')

# The three boxes on the Tasks page; dragging a task between them changes it.
TASK_PRIORITIES = (
    ('high', 'High priority'),
    ('general', 'To-do'),
    ('future', 'Future plans'),
)

TASK_STATUSES = (
    ('open', 'Open'),
    ('done', 'Done'),
)


class Task(BaseModel):
    """A to-do with a title, added from the navbar like a request: the same
    type, agent, state, carrier and dates, all optional. Starts open; someone
    marks it done."""

    title = models.CharField(max_length=255)
    type = models.CharField(max_length=10, choices=TASK_TYPES, blank=True)
    priority = models.CharField(max_length=10, choices=TASK_PRIORITIES, default='general')
    status = models.CharField(max_length=10, choices=TASK_STATUSES, default='open')
    note = models.TextField(blank=True)
    # The day it was added, editable; today unless picked.
    created_on = models.DateField(default=timezone.localdate)
    due_date = models.DateField(null=True, blank=True)

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, null=True, blank=True, related_name='tasks')
    carrier = models.ForeignKey(Carrier, on_delete=models.CASCADE, null=True, blank=True, related_name='tasks')
    state = models.ForeignKey(State, on_delete=models.PROTECT, null=True, blank=True, related_name='tasks')
    # day_off, inclusive
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        ordering = ('created_at',)

    def __str__(self):
        return self.title
