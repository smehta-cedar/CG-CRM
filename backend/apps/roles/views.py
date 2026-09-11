from collections import OrderedDict

from django.db.models import Count, ProtectedError
from drf_spectacular.utils import OpenApiExample, extend_schema, inline_serializer
from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Permission, Role
from .permissions import ANY_AUTHENTICATED, HasRolePermission
from .serializers import RoleDeleteSerializer, RoleSerializer


@extend_schema(tags=['Roles'])
class RoleViewSet(viewsets.ModelViewSet):
    """create / update / detail / list / delete for roles."""

    queryset = (
        Role.objects.all()
        .annotate(user_count=Count('users', distinct=True))
        .prefetch_related('permissions')
    )
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated, HasRolePermission]

    required_permissions = {
        # The catalog has no 'role.list'; listing and reading one role are the
        # same privilege, so both map to role.detail.
        'list': 'role.detail',
        'retrieve': 'role.detail',
        'create': 'role.create',
        'update': 'role.update',
        'partial_update': 'role.update',
        'destroy': 'role.delete',
    }

    def perform_destroy(self, instance):
        # The guard lives in the serializer so it applies everywhere; the view
        # only runs it.
        RoleDeleteSerializer.check(instance)
        try:
            instance.delete()
        except ProtectedError:
            # A user was assigned this role between the check and the delete.
            # User.role is on_delete=PROTECT, so the database refuses rather
            # than silently orphaning the account.
            raise serializers.ValidationError({
                'detail': 'This role was assigned to a user while it was being deleted.'
            })


@extend_schema(tags=['Roles'])
class PermissionTreeView(APIView):
    """The catalog as Module -> Resource -> Actions, for the checkbox tree."""

    permission_classes = [IsAuthenticated, HasRolePermission]

    # Static reference data with nothing sensitive in it, and the role editor
    # needs it before it knows which boxes to tick. Anyone signed in may read
    # it; what they can *do* with it is gated on the role endpoints.
    required_permissions = {'get': ANY_AUTHENTICATED}

    @extend_schema(
        responses=inline_serializer(
            name='PermissionTree',
            fields={
                'modules': serializers.ListField(child=serializers.DictField()),
            },
        ),
        examples=[
            OpenApiExample(
                'Grouped catalog',
                value={
                    'modules': [{
                        'module': 'User Management',
                        'resources': [{
                            'resource': 'User',
                            'actions': [{
                                'id': 1,
                                'action': 'create',
                                'codename': 'user.create',
                                'label': 'Create',
                            }],
                        }],
                    }],
                },
                response_only=True,
            ),
        ],
    )
    def get(self, request):
        # One query; the ordering on Permission.Meta keeps modules and
        # resources contiguous so grouping is a single pass.
        modules = OrderedDict()
        for perm in Permission.objects.all():
            resources = modules.setdefault(perm.module, OrderedDict())
            resources.setdefault(perm.resource, []).append({
                'id': perm.id,
                'action': perm.action,
                'codename': perm.codename,
                'label': perm.label,
            })

        return Response({
            'modules': [
                {
                    'module': module,
                    'resources': [
                        {'resource': resource, 'actions': actions}
                        for resource, actions in resources.items()
                    ],
                }
                for module, resources in modules.items()
            ],
        })
