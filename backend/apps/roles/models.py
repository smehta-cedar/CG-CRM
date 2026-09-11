from django.db import models
from django.utils.translation import gettext_lazy as _


class Permission(models.Model):
    """One row per (resource, action) pair in the catalog.

    A table rather than a JSON blob on Role: it stays joinable, the checkbox
    tree can be built with one query, and a role's grants survive a rename of
    whatever module they are filed under.

    Distinct from `django.contrib.auth.Permission`, which stays where it is for
    admin-site access; this is the CRM's own catalog.
    """

    module = models.CharField(_('module'), max_length=64, db_index=True)
    resource = models.CharField(_('resource'), max_length=64, db_index=True)
    action = models.CharField(_('action'), max_length=64)
    codename = models.CharField(
        _('codename'),
        max_length=128,
        unique=True,
        help_text=_("Lowercased '<resource>.<action>', e.g. 'user.create'."),
    )

    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('permission')
        verbose_name_plural = _('permissions')
        ordering = ['module', 'resource', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['resource', 'action'],
                name='unique_resource_action',
            ),
        ]

    def __str__(self):
        return self.codename

    @property
    def label(self):
        """'change_password' -> 'Change Password', for the checkbox label."""
        return self.action.replace('_', ' ').title()


class Role(models.Model):
    name = models.CharField(_('name'), max_length=64, unique=True)
    permissions = models.ManyToManyField(
        Permission,
        related_name='roles',
        blank=True,
        verbose_name=_('permissions'),
    )

    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('role')
        verbose_name_plural = _('roles')
        ordering = ['name']

    def __str__(self):
        return self.name

    def has_perm(self, codename):
        return self.permissions.filter(codename=codename).exists()
