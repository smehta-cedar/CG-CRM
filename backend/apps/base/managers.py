from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet whose delete() marks rows deleted instead of removing them."""

    def delete(self, user=None):
        now = timezone.now()
        count = self.filter(deleted_at__isnull=True).update(
            deleted_at=now,
            deleted_by=user,
            updated_at=now,
        )
        return count, {self.model._meta.label: count}

    # Same flags Django puts on QuerySet.delete: the manager does not get a
    # delete() of its own, so Model.objects.delete() still isn't possible.
    delete.alters_data = True
    delete.queryset_only = True

    def hard_delete(self):
        return super().delete()

    hard_delete.alters_data = True
    hard_delete.queryset_only = True

    def restore(self):
        return self.filter(deleted_at__isnull=False).update(
            deleted_at=None,
            deleted_by=None,
            updated_at=timezone.now(),
        )

    restore.alters_data = True

    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.filter(deleted_at__isnull=False)


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """Default manager: soft-deleted rows are invisible."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


# Every row, deleted or not, with the same queryset methods.
AllObjectsManager = models.Manager.from_queryset(SoftDeleteQuerySet)
