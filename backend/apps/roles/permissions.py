"""Access control: one decision function, two ways to call it.

`check_access` holds the whole policy. `HasRolePermission` (a DRF permission
class, for viewsets) and `@require_permission` (a decorator, for plain view
methods) are both thin wrappers over it, so there is exactly one place where
the rules live and exactly one place to change them.
"""

from dataclasses import dataclass
from functools import wraps

from rest_framework import status
from rest_framework.exceptions import APIException, NotAuthenticated
from rest_framework.permissions import BasePermission

#: Sentinel for an action open to any authenticated user. Spelled out so it
#: cannot be confused with "someone forgot to map this".
ANY_AUTHENTICATED = 'any-authenticated'


class AccessDenied(APIException):
    """403 whose body carries a machine-readable `code` beside the message.

    DRF puts an exception's code on the ErrorDetail rather than in the response
    body, and the frontend has to tell "you lack this permission" (show an
    error) from "you must change your password" (redirect).
    """

    status_code = status.HTTP_403_FORBIDDEN

    def __init__(self, detail, code):
        super().__init__({'detail': detail, 'code': code})


@dataclass(frozen=True)
class AccessResult:
    """Why a check passed or failed, without deciding how to report it.

    Returned rather than raised so the function stays callable from anywhere -
    a template, a management command, a test - and not just from a view.
    """

    allowed: bool
    detail: str = ''
    code: str = ''

    def __bool__(self):
        return self.allowed

    def raise_for_result(self):
        """Translate a refusal into the DRF exception that fits it."""
        if self.allowed:
            return
        if self.code == 'not_authenticated':
            raise NotAuthenticated()
        raise AccessDenied(self.detail, self.code)


ALLOWED = AccessResult(True)


def check_access(user, codename, *, allow_password_change_pending=False):
    """May `user` perform the action guarded by `codename`?

    The order is deliberate and is the contract:

    1. Authenticated at all.
    2. Not blocked.
    3. No pending forced password change - unless this action is one of the
       few that has to stay reachable, or the user can never clear the flag.
    4. Superuser passes, without consulting a role.
    5. Otherwise the user's role must hold the codename.

    `codename` may be a real codename, `ANY_AUTHENTICATED` for an action that
    only requires signing in, or None - which denies, so that an action nobody
    mapped fails closed instead of being waved through.
    """
    if user is None or not user.is_authenticated:
        return AccessResult(
            False,
            'Authentication credentials were not provided.',
            'not_authenticated',
        )

    if user.is_blocked:
        # Normally unreachable over JWT, because VersionedJWTAuthentication
        # rejects blocked accounts before a view is ever chosen. It still
        # matters for session-authenticated callers, and it is the kind of
        # check that should not depend on another layer staying correct.
        return AccessResult(
            False,
            'This account has been blocked.',
            'account_blocked',
        )

    if user.must_change_password and not allow_password_change_pending:
        return AccessResult(
            False,
            'You must change your password before continuing.',
            'password_change_required',
        )

    if user.is_superuser:
        return ALLOWED

    if codename is ANY_AUTHENTICATED:
        return ALLOWED

    if codename is None:
        return AccessResult(
            False,
            'You do not have permission to perform this action.',
            'permission_denied',
        )

    if user.has_permission(codename):
        return ALLOWED

    return AccessResult(
        False,
        'You do not have permission to perform this action.',
        'permission_denied',
    )


class HasRolePermission(BasePermission):
    """Gates a viewset on the catalog, via `check_access`.

    A view opts in by declaring `required_permissions`, mapping each viewset
    action (or, for a plain APIView, each lowercased HTTP method) to a
    codename::

        class RoleViewSet(ModelViewSet):
            required_permissions = {
                'list': 'role.detail',
                'create': 'role.create',
            }

    Fails closed: an action missing from the map is denied. Forgetting a
    codename when you add an action should cost a 403 in a test, not an
    unguarded endpoint in production. Use `ANY_AUTHENTICATED` to open one on
    purpose, and list an action in `password_change_exempt_actions` to keep it
    reachable while a forced password change is pending.

    Views with no `required_permissions` at all are not using this class.
    """

    def has_permission(self, request, view):
        required = getattr(view, 'required_permissions', None)
        if required is None:
            return True

        # Plain APIView: key off the method instead of the viewset action.
        action = getattr(view, 'action', None) or request.method.lower()
        exempt = action in getattr(view, 'password_change_exempt_actions', ())

        # Raises rather than returning False, so the refusal keeps its code.
        check_access(
            request.user,
            required.get(action),
            allow_password_change_pending=exempt,
        ).raise_for_result()
        return True


def _request_from(args):
    for arg in args:
        if hasattr(arg, 'user') and hasattr(arg, 'method'):
            return arg
    raise TypeError(
        '@require_permission must decorate a view method that is passed the '
        'request, e.g. def post(self, request).'
    )


def require_permission(codename, *, allow_password_change_pending=False):
    """Decorator form, for plain view methods::

        @require_permission('user.create')
        def post(self, request): ...

    Same policy as `HasRolePermission`, because both call `check_access`. The
    permission class composes better with viewsets and is what the viewsets
    here use; this exists for one-off view methods where a class-level map
    would be indirection for its own sake.

    Works on both bound methods (self, request) and function-based views
    (request), since it finds the request by shape rather than by position.
    """

    def decorator(view_method):
        @wraps(view_method)
        def wrapper(*args, **kwargs):
            request = _request_from(args)
            check_access(
                request.user,
                codename,
                allow_password_change_pending=allow_password_change_pending,
            ).raise_for_result()
            return view_method(*args, **kwargs)

        # Lets the schema generator and tests see what a method demands.
        wrapper.required_permission = codename
        return wrapper

    return decorator
