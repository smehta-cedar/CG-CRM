"""Swagger docs for the tasks endpoints, one per view in views.py."""
from drf_spectacular.utils import extend_schema

from apps.base.api.schema import (
    PAGINATION_PARAMETERS,
    api_response,
    combine_schemas,
    error_responses,
)

from .serializers import TaskCreateSerializer, TaskListQuerySerializer, TaskSerializer, TaskUpdateSerializer

TAGS = ['Tasks']


task_list = extend_schema(
    operation_id='tasks_list',
    tags=TAGS,
    summary='List tasks',
    description='Every task, oldest first.',
    parameters=[TaskListQuerySerializer, *PAGINATION_PARAMETERS],
    responses={200: api_response(TaskSerializer, paginated=True), **error_responses(400, 401, 403)},
)


task_create = extend_schema(
    operation_id='tasks_create',
    tags=TAGS,
    summary='Add a task',
    description=(
        'Only `title` is required. The rest are the request fields, `priority` (defaults to general), '
        '`created_on` (defaults to today) and `due_date`; the first and last day are kept for day_off only. Starts open.'
    ),
    request=TaskCreateSerializer,
    responses={201: api_response(TaskSerializer), **error_responses(400, 401, 403)},
)


task_detail = combine_schemas(
    extend_schema(
        methods=['GET'],
        tags=TAGS,
        summary='Get a task',
        responses={200: api_response(TaskSerializer), **error_responses(401, 403, 404)},
    ),
    extend_schema(
        methods=['PATCH'],
        tags=TAGS,
        summary='Change a task',
        description=(
            'Any field of the add call, plus `status`. The edit popup sends every field; '
            'dragging a task to another box on the Tasks page sends only its new `priority`.'
        ),
        request=TaskUpdateSerializer,
        responses={200: api_response(TaskSerializer), **error_responses(400, 401, 403, 404)},
    ),
    extend_schema(
        methods=['DELETE'],
        tags=TAGS,
        summary='Delete a task',
        description='Soft delete: the task is hidden and can be restored.',
        responses={200: api_response(), **error_responses(401, 403, 404)},
    ),
)
