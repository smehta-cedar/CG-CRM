from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import Role, RolePermission
from apps.accounts.models.roles import ACTIONS, PERMISSION_LABELS
from apps.accounts.selectors.role_selector import RoleSelector
from apps.base.services.base import BaseService

PERMISSION_FLAGS = tuple(f'can_{action}' for action in ACTIONS)


class RoleService(BaseService):
    """Role writes, including the role's RolePermission rows."""

    @transaction.atomic
    def create_role(self, *, name, description='', permissions=None):
        name = name.strip()
        self._ensure_name_free(name)
        role = self._create(Role, name=name, description=description)
        if permissions is not None:
            self.set_permissions(role, permissions)
        return role

    @transaction.atomic
    def update_role(self, role, *, permissions=None, **fields):
        if 'name' in fields:
            fields['name'] = fields['name'].strip()
            self._ensure_name_free(fields['name'], exclude_pk=role.pk)
        role = self._update(role, **fields)
        if permissions is not None:
            self.set_permissions(role, permissions)
        return role

    @transaction.atomic
    def delete_role(self, role):
        user_count = RoleSelector().user_count(role)
        if user_count:
            raise ValidationError(
                f'This role is assigned to {user_count} user(s). Move them to another role first.'
            )
        self._delete(role)

    @transaction.atomic
    def set_permissions(self, role, permissions):
        """Make `permissions` the role's complete list of grants.

            [{"module": "dashboard", "can_view": True, "can_update": True}, ...]

        Flags left out are False, and modules left out lose all access.
        Existing rows are updated in place rather than deleted, so a role
        never piles up soft-deleted permission rows.
        """
        grants = {}
        for item in permissions:
            module = item.get('module')
            if module not in PERMISSION_LABELS:
                raise ValidationError({'permissions': f'Unknown module: {module!r}.'})
            if module in grants:
                raise ValidationError({'permissions': f'Module {module!r} is listed twice.'})
            flags = {flag: bool(item.get(flag, False)) for flag in PERMISSION_FLAGS}
            try:
                RolePermission(role=role, module=module, **flags).clean()
            except ValidationError as exc:
                raise ValidationError({'permissions': [f'{module}: {m}' for m in exc.messages]}) from exc
            grants[module] = flags

        existing = {row.module: row for row in RoleSelector().get_permissions(role)}
        for module in existing.keys() - grants.keys():
            grants[module] = dict.fromkeys(PERMISSION_FLAGS, False)

        for module, flags in grants.items():
            row = existing.get(module)
            if row is None:
                if any(flags.values()):
                    self._create(RolePermission, role=role, module=module, **flags)
            elif any(getattr(row, flag) != value for flag, value in flags.items()):
                self._update(row, **flags)

    @staticmethod
    def _ensure_name_free(name, exclude_pk=None):
        if RoleSelector().name_taken(name, exclude_pk=exclude_pk):
            raise ValidationError({'name': 'A role with this name already exists.'})
