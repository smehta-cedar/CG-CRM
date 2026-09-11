from rest_framework.permissions import BasePermission

#: Sentinel for an action that is deliberately open to any authenticated user.
#: Spelled out so it cannot be confused with "someone forgot to map this".
ANY_AUTHENTICATED = 'any-authenticated'


class HasRolePermission(BasePermission):
    """Gates a view on the CRM permission catalog.

    A view opts in by declaring `required_permissions`, mapping each viewset
    action (or, for a plain APIView, each lowercased HTTP method) to a
    codename::

        class RoleViewSet(ModelViewSet):
            required_permissions = {
                'list': 'role.detail',
                'create': 'role.create',
                ...
            }

    Fails closed: a view that declares the mapping but leaves an action out
    denies it. Forgetting to add a codename when you add an action should cost
    you a 403 in a test, not an unguarded endpoint in production. Use
    `ANY_AUTHENTICATED` to open one on purpose.

    Views with no `required_permissions` at all are not using this class and
    fall through to whatever else is configured.
    """

    message = 'You do not have permission to perform this action.'

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        required = getattr(view, 'required_permissions', None)
        if required is None:
            return True

        action = getattr(view, 'action', None)
        if action is None:
            # Plain APIView: key off the method instead.
            action = request.method.lower()

        codename = required.get(action)
        if codename is ANY_AUTHENTICATED:
            return True
        if codename is None:
            return False

        # Superusers short-circuit inside has_permission().
        return user.has_permission(codename)
