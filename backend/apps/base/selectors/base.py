from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import get_object_or_404


class BaseSelector:
    """Read-only queries for one model. Subclasses set `model`.

    Filter methods narrow `self.queryset` and return the selector, so they
    chain; finish with get_queryset(), get_object_or_404() and friends:

        users = UserSelector(request).search('jane').filter_active(True).get_queryset()

    Filters accumulate, so use a fresh selector for each query.
    """

    model = None

    def __init__(self, request=None):
        if self.model is None:
            raise ImproperlyConfigured(f'{type(self).__name__} must set `model`.')
        self.request = request
        self.queryset = self.get_base_queryset()

    def get_base_queryset(self):
        """Starting point for every query. Override to add select_related or
        to scope rows by self.request.user."""
        return self.model._default_manager.all()

    def filter(self, *args, **kwargs):
        self.queryset = self.queryset.filter(*args, **kwargs)
        return self

    def exclude(self, *args, **kwargs):
        self.queryset = self.queryset.exclude(*args, **kwargs)
        return self

    def order_by(self, *fields):
        self.queryset = self.queryset.order_by(*fields)
        return self

    def get_queryset(self):
        return self.queryset

    def get_object_or_404(self, **lookup):
        return get_object_or_404(self.queryset, **lookup)

    def get_or_none(self, **lookup):
        return self.queryset.filter(**lookup).first()

    def exists(self, **lookup):
        return self.queryset.filter(**lookup).exists()

    def count(self):
        return self.queryset.count()
