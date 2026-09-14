import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from .managers import AllObjectsManager, SoftDeleteManager


class BaseModel(models.Model):
    """Common fields for every project model.

    Abstract, so it creates no table of its own: each subclass gets these
    columns in its own table.

        from apps.base.models import BaseModel

        class Lead(BaseModel):
            name = models.CharField(max_length=255)

    Deletes are soft by default:

        lead.delete()                      # sets deleted_at, row stays
        lead.delete(user=request.user)     # also records deleted_by
        Lead.objects.filter(...).delete()  # bulk soft delete
        lead.restore()
        lead.hard_delete()                 # really removes the row

        Lead.objects                       # hides deleted rows
        Lead.all_objects                   # everything
        Lead.all_objects.deleted()         # only deleted rows

    Soft deletes do not cascade and do not send pre_delete/post_delete.
    A unique field still counts deleted rows; to let a value be reused after
    a delete, use a conditional constraint instead of unique=True:

        models.UniqueConstraint(
            fields=['email'],
            condition=models.Q(deleted_at__isnull=True),
            name='uniq_lead_email_alive',
        )
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Lower numbers sort first.
    priority = models.PositiveIntegerField(default=0, db_index=True)

    # Lets a record be switched off without deleting it.
    is_active = models.BooleanField(default=True, db_index=True)

    # Nullable because not every write has a user behind it (migrations,
    # scripts, createsuperuser). related_name='+' skips the reverse accessor,
    # which would otherwise clash across every subclass.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name='+',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name='+',
    )

    deleted_at = models.DateTimeField(null=True, blank=True, editable=False, db_index=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name='+',
    )

    # The first manager is the default, so admin, DRF and reverse relations
    # (lead.notes.all()) skip deleted rows. The base manager stays Django's
    # plain one, so a FK to a deleted row still resolves and hard_delete()
    # still cascades to deleted children.
    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True
        ordering = ('priority', '-created_at')
        get_latest_by = 'created_at'

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def save(self, *args, **kwargs):
        # auto_now only fires when updated_at is among the fields written, so
        # save(update_fields=[...]) would otherwise leave it stale.
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and 'updated_at' not in update_fields:
            kwargs['update_fields'] = {*update_fields, 'updated_at'}
        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False, user=None):
        if self.is_deleted:
            return 0, {}
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save(using=using, update_fields=['deleted_at', 'deleted_by'])
        return 1, {self._meta.label: 1}

    delete.alters_data = True

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)

    hard_delete.alters_data = True

    def restore(self, using=None):
        if not self.is_deleted:
            return
        self.deleted_at = None
        self.deleted_by = None
        self.save(using=using, update_fields=['deleted_at', 'deleted_by'])

    restore.alters_data = True
