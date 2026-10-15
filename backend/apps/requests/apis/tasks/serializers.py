from rest_framework import serializers

from apps.requests.apis.requests.serializers import RequestCreateSerializer, RequestSerializer
from apps.agents.models import Agent
from apps.requests.models import TASK_PRIORITIES, TASK_STATUSES, TASK_TYPES, Task


class TaskSerializer(RequestSerializer):
    """How a task appears in every response: a request's shape plus its title."""

    class Meta:
        model = Task
        fields = (
            'id',
            'title',
            'priority',
            'type',
            'status',
            'note',
            'agent',
            'carrier',
            'state',
            'start_date',
            'end_date',
            'created_on',
            'due_date',
            'created_by',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class TaskCreateSerializer(RequestCreateSerializer):
    """The Create-a-request fields plus a title, priority and dates. Only the title is required."""

    title = serializers.CharField(max_length=255)
    type = serializers.ChoiceField(choices=TASK_TYPES, required=False, allow_blank=True)
    agent_id = serializers.PrimaryKeyRelatedField(
        source='agent', queryset=Agent.objects.all(), pk_field=serializers.UUIDField(), required=False, allow_null=True
    )
    priority = serializers.ChoiceField(choices=TASK_PRIORITIES, required=False)
    created_on = serializers.DateField(required=False, allow_null=True)
    due_date = serializers.DateField(required=False, allow_null=True)


class TaskUpdateSerializer(TaskCreateSerializer):
    """Any of the popup's fields (the edit popup sends them all; a drag sends
    just the priority), and open or done. Send only the fields that change."""

    status = serializers.ChoiceField(choices=TASK_STATUSES, required=False)


class TaskListQuerySerializer(serializers.Serializer):
    priority = serializers.ChoiceField(choices=TASK_PRIORITIES, required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=TASK_STATUSES, required=False, allow_blank=True)
    agent_id = serializers.UUIDField(required=False)
