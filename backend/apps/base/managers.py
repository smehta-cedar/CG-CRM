from collections import Counter

from django.db import models, transaction
from django.utils import timezone


def soft_delete_children(model, pks, user, now):
    """Soft delete the live rows that point at `pks` through an on_delete=CASCADE
    key, and their children in turn, the way a hard delete would remove them."""
    counts = Counter()
    for rel in model._meta.related_objects:
        child = rel.related_model
        if rel.many_to_many or rel.on_delete is not models.CASCADE or not isinstance(child._default_manager, SoftDeleteManager):
            continue
        _, deleted = child._default_manager.filter(**{f'{rel.field.name}__in': pks}).delete(user=user, now=now)
        counts.update(deleted)
    return counts


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet whose delete() marks rows deleted instead of removing them.
    Children joined by an on_delete=CASCADE key are soft deleted with them."""

    def delete(self, user=None, now=None):
        now = now or timezone.now()
        with transaction.atomic(using=self.db):
            pks = list(self.filter(deleted_at__isnull=True).values_list('pk', flat=True))
            if not pks:
                return 0, {}
            count = self.model._base_manager.using(self.db).filter(pk__in=pks).update(
                deleted_at=now,
                deleted_by=user,
                updated_at=now,
            )
            counts = soft_delete_children(self.model, pks, user, now)
        counts[self.model._meta.label] += count
        return sum(counts.values()), dict(counts)

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
