from apps.accounts.models import Designation
from apps.base.selectors.base import BaseSelector


class DesignationSelector(BaseSelector):
    model = Designation

    def active(self):
        self.queryset = self.queryset.filter(is_active=True)
        return self

    def search(self, value):
        if value:
            self.queryset = self.queryset.filter(name__icontains=value)
        return self

    def name_taken(self, name, exclude_pk=None):
        # Mirrors uniq_designation_name_alive: case-insensitive, live rows only.
        queryset = Designation.objects.filter(name__iexact=name.strip())
        if exclude_pk is not None:
            queryset = queryset.exclude(pk=exclude_pk)
        return queryset.exists()

    def user_count(self, designation):
        return designation.users.count()
