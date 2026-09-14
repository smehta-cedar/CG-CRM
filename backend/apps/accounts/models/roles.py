from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower

from apps.base.models import BaseModel

# Every screen a role can be granted. Top-level keys are menu sections: a
# section with children is granted per child, one without is granted whole.
#
# Permission codes are "section" or "section.child" (e.g. "dashboard",
# "finance.invoices"), so the same child key can sit under two sections.
#
#     'finance': {
#         'label': 'Finance',
#         'children': {
#             'invoices': 'Invoices',
#             'payments': 'Payments',
#         },
#     },
#
# Codes are stored on RolePermission rows. Adding one is free; renaming or
# removing one orphans the rows that hold the old code.
MODULES = {
    'dashboard': {
        'label': 'Dashboard Overview',
        'children': {},
    },
    'users': {
        'label': 'Users',
        'children': {},
    },
}

ACTIONS = ('view', 'create', 'update', 'delete')


def _build_permission_labels():
    labels = {}
    for section, spec in MODULES.items():
        if not spec['children']:
            labels[section] = spec['label']
        for child, child_label in spec['children'].items():
            labels[f'{section}.{child}'] = f"{spec['label']} / {child_label}"
    return labels


# {"dashboard": "Dashboard Overview", ...}
PERMISSION_LABELS = _build_permission_labels()


def permission_choices():
    """Codes grouped by section, in the shape Django's `choices` accepts."""
    choices = []
    for section, spec in MODULES.items():
        if not spec['children']:
            choices.append((section, spec['label']))
        else:
            choices.append((
                spec['label'],
                [(f'{section}.{child}', label) for child, label in spec['children'].items()],
            ))
    return choices


class Role(BaseModel):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta(BaseModel.Meta):
        constraints = [
            # Case-insensitive, and a deleted role's name can be reused.
            models.UniqueConstraint(
                Lower('name'),
                condition=models.Q(deleted_at__isnull=True),
                name='uniq_role_name_alive',
                violation_error_message='A role with this name already exists.',
            ),
        ]

    def __str__(self):
        return self.name


class RolePermission(BaseModel):
    """What one role may do on one screen. No row means no access."""

    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='permissions')
    module = models.CharField(max_length=100, choices=permission_choices)

    can_view = models.BooleanField(default=False)
    can_create = models.BooleanField(default=False)
    can_update = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)

    class Meta(BaseModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=['role', 'module'],
                condition=models.Q(deleted_at__isnull=True),
                name='uniq_role_permission_alive',
                violation_error_message='This role already has a permission row for this module.',
            ),
        ]

    def __str__(self):
        return f'{self.role} - {self.module}'

    def clean(self):
        super().clean()
        if (self.can_create or self.can_update or self.can_delete) and not self.can_view:
            raise ValidationError({'can_view': 'Create, update or delete also needs view.'})
