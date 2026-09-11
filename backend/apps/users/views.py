from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.roles.permissions import ANY_AUTHENTICATED, HasRolePermission

from .models import User
from .serializers import UserSerializer


@extend_schema(tags=['Users'])
class UserViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """create / update / detail / list for users.

    No destroy: accounts are deactivated (`is_active`) rather than deleted, so
    the records that reference them keep making sense.
    """

    queryset = User.objects.select_related('role').order_by('full_name', 'email')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, HasRolePermission]

    required_permissions = {
        'list': 'user.detail',
        'retrieve': 'user.detail',
        'create': 'user.create',
        'update': 'user.update',
        'partial_update': 'user.update',
        # Reading yourself is not a privilege - see `me` below.
        'me': ANY_AUTHENTICATED,
    }

    @extend_schema(
        responses=UserSerializer,
        description=(
            'The signed-in account, with its role and effective permission '
            'codenames. The frontend renders its menus from this.'
        ),
    )
    # Anyone signed in may read their own account - it is ANY_AUTHENTICATED
    # in the map above. Routing this through `user.detail` would be circular:
    # a low-privilege user needs their permission list to draw a menu, but
    # would need user.detail to fetch it, so they would get no menu at all.
    @action(detail=False, methods=['get'])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
