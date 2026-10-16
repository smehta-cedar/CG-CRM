from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.base.api.pagination import paginate
from apps.base.api.permissions import ensure_own, module_permission, own_only
from apps.base.api.response import APIResponse
from apps.requests.models import Task
from apps.requests.validators import resolve_state

from . import swagger
from .serializers import TaskCreateSerializer, TaskListQuerySerializer, TaskSerializer, TaskUpdateSerializer

CAN_MANAGE_TASKS = module_permission('tasks')


def _tasks(user):
    """An agent's sign-in reaches only its own agent's tasks."""
    return own_only(user, Task.objects.select_related('agent', 'carrier', 'state', 'created_by'))


def _task_fields(user, data, task=None):
    """Model values for the fields sent (every field on a new task), checked
    against the task's other values. Everything but the title is optional."""
    fields = {name: data[name] for name in ('priority', 'status', 'type', 'carrier', 'due_date') if name in data}
    fields.update({name: data[name].strip() for name in ('title', 'note') if name in data})
    if 'state' in data:
        fields['state'] = resolve_state(data['state']) if data['state'] else None
    if task is None or 'created_on' in data:
        fields['created_on'] = data.get('created_on') or timezone.localdate()
    if task is None or 'agent' in data:
        # An agent's own sign-in always files for itself, so the task stays in its list.
        agent = data.get('agent')
        if user.agent_id:
            if agent is not None:
                ensure_own(user, agent.pk)
            agent = user.agent
        fields['agent'] = agent

    def current(name):
        return fields[name] if name in fields else getattr(task, name, None)

    # The first and last day belong to a day off only.
    if current('type') == 'day_off':
        fields.update({name: data[name] for name in ('start_date', 'end_date') if name in data})
    elif current('start_date') or current('end_date'):
        fields.update(start_date=None, end_date=None)

    if current('start_date') and current('end_date') and current('end_date') < current('start_date'):
        raise ValidationError({'end_date': ["The last day can't be before the first."]})
    if current('due_date') and current('due_date') < current('created_on'):
        raise ValidationError({'due_date': ["The due date can't be before the created date."]})
    return fields


@swagger.task_list
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_TASKS])
def task_list(request):
    query = TaskListQuerySerializer(data=request.query_params.dict())
    query.is_valid(raise_exception=True)
    filters = query.validated_data

    tasks = _tasks(request.user)
    if filters.get('priority'):
        tasks = tasks.filter(priority=filters['priority'])
    if filters.get('status'):
        tasks = tasks.filter(status=filters['status'])
    if filters.get('agent_id'):
        tasks = tasks.filter(agent_id=filters['agent_id'])

    page, meta = paginate(request, tasks)
    return APIResponse(TaskSerializer(page, many=True).data, 'Tasks fetched successfully.', meta=meta)


@swagger.task_create
@api_view(['POST'])
@permission_classes([IsAuthenticated, CAN_MANAGE_TASKS])
def task_create(request):
    serializer = TaskCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    task = Task.objects.create(
        **_task_fields(request.user, serializer.validated_data),
        created_by=request.user,
        updated_by=request.user,
    )
    return APIResponse(TaskSerializer(task).data, 'Task added successfully.', status=status.HTTP_201_CREATED)


@swagger.task_detail
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, CAN_MANAGE_TASKS])
def task_detail(request, pk):
    task = get_object_or_404(_tasks(request.user), pk=pk)

    if request.method == 'GET':
        return APIResponse(TaskSerializer(task).data, 'Task fetched successfully.')

    if request.method == 'PATCH':
        # partial=True: only the fields that were sent get updated.
        serializer = TaskUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields = _task_fields(request.user, serializer.validated_data, task)
        for name, value in fields.items():
            setattr(task, name, value)
        task.updated_by = request.user
        task.save(update_fields=[*fields, 'updated_by'])
        return APIResponse(TaskSerializer(task).data, 'Task updated successfully.')

    # DELETE: soft delete.
    task.delete(user=request.user)
    return APIResponse(None, 'Task deleted successfully.')
