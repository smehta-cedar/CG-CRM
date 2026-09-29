"""Swagger docs for the notifications endpoints, one per view in views.py."""
from drf_spectacular.utils import extend_schema

from apps.base.api.schema import PAGINATION_PARAMETERS, api_response, error_responses

from .serializers import NotificationSerializer

TAGS = ['Notifications']


notification_list = extend_schema(
    operation_id='notifications_list',
    tags=TAGS,
    summary='List my notifications',
    description="The signed-in user's notifications, newest first. `meta.unread` is how many are unread in all.",
    parameters=[*PAGINATION_PARAMETERS],
    responses={200: api_response(NotificationSerializer, paginated=True), **error_responses(401)},
)


notification_read = extend_schema(
    operation_id='notifications_read',
    tags=TAGS,
    summary='Mark one notification read',
    request=None,
    responses={200: api_response(NotificationSerializer), **error_responses(401, 404)},
)


notification_read_all = extend_schema(
    operation_id='notifications_read_all',
    tags=TAGS,
    summary='Mark all my notifications read',
    request=None,
    responses={200: api_response(), **error_responses(401)},
)
