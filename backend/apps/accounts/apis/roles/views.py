from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import Role
from apps.base.api.permissions import module_permission
from apps.base.api.response import APIResponse
from apps.base.api.schema import api_response, error_responses

from ..users.serializers import RoleSummarySerializer

# Whoever may see users may see the roles they can be given.
CAN_VIEW_USERS = module_permission('users')


@extend_schema(
    operation_id='roles_list',
    tags=['Users'],
    summary='List roles',
    description='The live, active roles a user can be given, by name. Not paginated.',
    responses={200: api_response(RoleSummarySerializer, many=True), **error_responses(401, 403)},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_VIEW_USERS])
def role_list(request):
    roles = Role.objects.filter(is_active=True).order_by('name')
    return APIResponse(RoleSummarySerializer(roles, many=True).data, 'Roles fetched successfully.')
