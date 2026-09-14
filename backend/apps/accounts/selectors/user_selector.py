from django.db.models import Q

from apps.accounts.models import User
from apps.base.selectors.base import BaseSelector


class UserSelector(BaseSelector):
    model = User

    def get_base_queryset(self):
        return User.objects.select_related('role', 'designation')

    def search(self, value):
        if value:
            self.queryset = self.queryset.filter(
                Q(email__icontains=value)
                | Q(full_name__icontains=value)
                | Q(phone__icontains=value)
                | Q(role__name__icontains=value)
                | Q(designation__name__icontains=value)
            )
        return self

    def filter_role(self, role_id):
        if role_id:
            self.queryset = self.queryset.filter(role_id=role_id)
        return self

    def filter_designation(self, designation_id):
        if designation_id:
            self.queryset = self.queryset.filter(designation_id=designation_id)
        return self

    def filter_active(self, is_active):
        if is_active is not None:
            self.queryset = self.queryset.filter(is_active=is_active)
        return self

    def email_taken(self, email):
        # all_objects: a soft-deleted user still holds their email.
        return User.all_objects.filter(email=email.strip().lower()).exists()
