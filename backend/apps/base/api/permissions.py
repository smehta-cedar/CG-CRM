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
        return action is not None and user.has_permission(self.module, action)


def module_permission(module, actions=None):
    """Permission class for @permission_classes that checks the role.

        @api_view(['POST'])
        @permission_classes([IsAuthenticated, module_permission('users', {'POST': 'update'})])
        def user_block(request, pk):
            ...

    The HTTP method picks the action (GET view, POST create, PUT/PATCH
    update, DELETE delete); `actions` overrides it per method.
    """
    return type(
        'ModulePermission',
        (ModulePermission,),
        {'module': module, 'actions': {**METHOD_ACTIONS, **(actions or {})}},
    )
