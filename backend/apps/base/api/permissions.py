from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

METHOD_ACTIONS = {
    'GET': 'view',
    'HEAD': 'view',
    'OPTIONS': 'view',
    'POST': 'create',
    'PUT': 'update',
    'PATCH': 'update',
    'DELETE': 'delete',
}


class ModulePermission(BasePermission):
    """Checks the user's role for `module`. Build one with module_permission()."""

    module = None
    actions = METHOD_ACTIONS

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        action = self.actions.get(request.method)
        modules = (self.module,) if isinstance(self.module, str) else self.module
        return action is not None and any(user.has_permission(module, action) for module in modules)


def module_permission(module, actions=None):
    """Permission class for @permission_classes that checks the role.

        @api_view(['POST'])
        @permission_classes([IsAuthenticated, module_permission('users', {'POST': 'update'})])
        def user_block(request, pk):
            ...

    The HTTP method picks the action (GET view, POST create, PUT/PATCH
    update, DELETE delete); `actions` overrides it per method. A tuple of
    modules passes when any of them allows the action.
    """
    return type(
        'ModulePermission',
        (ModulePermission,),
        {'module': module, 'actions': {**METHOD_ACTIONS, **(actions or {})}},
    )


class IsSuperuser(BasePermission):
    """Superusers only, whatever their role; for managing roles themselves."""

    message = 'Only a superuser can manage roles.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.is_superuser)


# The own-records layer. An agent signs in with the Agent role's permissions,
# the same pages as staff; these narrow what it reaches to its own agent.


def own_only(user, queryset, field='agent'):
    """An agent's sign-in gets only its own agent's rows; staff get all."""
    return queryset.filter(**{field: user.agent_id}) if user.agent_id else queryset


def ensure_own(user, agent_id):
    """An agent's sign-in may only write its own agent's rows; staff may write any."""
    if user.agent_id and agent_id != user.agent_id:
        raise PermissionDenied('You can only change your own records.')
