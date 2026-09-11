from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


class LoginType(models.TextChoices):
    """How an account proves who it is."""

    LOCAL = 'local', _('Local password')
    SSO = 'sso', _('Single sign-on')


class User(AbstractBaseUser, PermissionsMixin):
    """The account every other record in the CRM hangs off.

    Email is the login handle; there is no username. Permissions are reached
    through `role` - see apps.roles.
    """

    email = models.EmailField(
        _('email address'),
        max_length=254,
        unique=True,
        help_text=_('Used to sign in. Stored lowercased.'),
    )
    full_name = models.CharField(_('full name'), max_length=150)

    login_type = models.CharField(
        _('login type'),
        max_length=16,
        choices=LoginType.choices,
        default=LoginType.LOCAL,
    )

    # --- status flags -----------------------------------------------------
    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_('Unset instead of deleting an account, to keep its history.'),
    )
    is_blocked = models.BooleanField(
        _('blocked'),
        default=False,
        help_text=_('Set by an administrator to deny sign-in without deactivating.'),
    )
    must_change_password = models.BooleanField(
        _('must change password'),
        default=False,
        help_text=_('Force a password reset on the next successful sign-in.'),
    )
    is_staff = models.BooleanField(
        _('staff status'),
        default=False,
        help_text=_('Can sign in to the Django admin site.'),
    )

    # --- role -------------------------------------------------------------
    role = models.ForeignKey(
        'roles.Role',
        verbose_name=_('role'),
        null=True,
        blank=True,
        # PROTECT, not SET_NULL: a role that is still assigned must not be
        # deletable. RoleDeleteSerializer turns the resulting ProtectedError
        # into a readable 400, but the database is what actually guarantees it.
        on_delete=models.PROTECT,
        related_name='users',
    )

    # --- timestamps -------------------------------------------------------
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    EMAIL_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['full_name', 'email']

    def __str__(self):
        return self.email

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)

    def save(self, *args, **kwargs):
        # clean() only runs via full_clean(), and plenty of call sites
        # (fixtures, the admin's raw save, bulk helpers) skip it.
        self.email = self.__class__.objects.normalize_email(self.email)
        return super().save(*args, **kwargs)

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.full_name.split(' ')[0] if self.full_name else self.email

    @property
    def can_sign_in(self):
        """Both flags have to be right before this account may authenticate."""
        return self.is_active and not self.is_blocked
