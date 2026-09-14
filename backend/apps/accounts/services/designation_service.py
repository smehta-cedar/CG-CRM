from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import Designation
from apps.accounts.selectors.designation_selector import DesignationSelector
from apps.base.services.base import BaseService


class DesignationService(BaseService):
    @transaction.atomic
    def create_designation(self, *, name, description=''):
        name = name.strip()
        self._ensure_name_free(name)
        return self._create(Designation, name=name, description=description)

    @transaction.atomic
    def update_designation(self, designation, **fields):
        if 'name' in fields:
            fields['name'] = fields['name'].strip()
            self._ensure_name_free(fields['name'], exclude_pk=designation.pk)
        return self._update(designation, **fields)

    @transaction.atomic
    def delete_designation(self, designation):
        user_count = DesignationSelector().user_count(designation)
        if user_count:
            raise ValidationError(
                f'This designation is assigned to {user_count} user(s). Move them to another designation first.'
            )
        self._delete(designation)

    @staticmethod
    def _ensure_name_free(name, exclude_pk=None):
        if DesignationSelector().name_taken(name, exclude_pk=exclude_pk):
            raise ValidationError({'name': 'A designation with this name already exists.'})
