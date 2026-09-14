from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils.functional import cached_property

from apps.base.managers import SoftDeleteManager
from apps.base.models import BaseModel

from .designations import Designation
from .roles import ACTIONS, PERMISSION_LABELS, Role


class UserManager(SoftDeleteManager, BaseUserManager):
    # Soft-deleted users are invisible here, so they cannot log in and
    # SimpleJWT rejects their tokens.
    use_in_migrations = True

    def get_by_natural_key(self, username):
        # Emails are stored lowercase; match the login input the same way.
        return self.get(email=username.strip().lower())

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('An email address is required.')
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields['is_staff'] is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields['is_superuser'] is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self._create_user(email, password, **extra_fields)


class User(BaseModel, AbstractBaseUser):
    """Logs in with email. Access comes from `role`, not Django permissions.

    BaseModel.is_active doubles as the block switch: Django refuses to log in
    an inactive user.
    """

    # unique=True rather than a conditional constraint: Django requires the
    # login field to be unique outright, so a deleted user's email stays taken
    # (restore the account instead of re-registering it).
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True)

    designation = models.ForeignKey(
        Designation,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='users',
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='users',
    )

    is_staff = models.BooleanField(default=False, help_text='Can log in to the Django admin.')
    is_superuser = models.BooleanField(
        default=False,
        help_text='Has every permission, whatever the role.',
    )

    objects = UserManager()

    USERNAME_FIELD = 'email'
    EMAIL_FIELD = 'email'
    # Prompted for by createsuperuser, after email and password.
    REQUIRED_FIELDS = ['full_name']

    class Meta(BaseModel.Meta):
        pass

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        self.full_name = ' '.join(self.full_name.split())
        super().save(*args, **kwargs)

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.full_name.split(' ', 1)[0]

    @cached_property
    def role_permissions(self):
        """{"dashboard": {"view": True, ...}, ...} from the role.

        One query, cached on this instance. A missing, inactive or
        soft-deleted role grants nothing.
        """
        role = self.role
        if role is None or role.is_deleted or not role.is_active:
            return {}
        return {
            permission.module: {action: getattr(permission, f'can_{action}') for action in ACTIONS}
            for permission in role.permissions.all()
        }

    def has_permission(self, module, action='view'):
        """Whether this user may perform `action` on `module`.

        user.has_permission('dashboard', 'update')
        """
        if module not in PERMISSION_LABELS:
            raise ValueError(f'Unknown permission module: {module!r}')
        if action not in ACTIONS:
            raise ValueError(f'Unknown permission action: {action!r}')
        if not self.is_active:
            return False
        if self.is_superuser:
            return True
        return self.role_permissions.get(module, {}).get(action, False)

    # Django's own permission system is not used. The admin still calls these,
    # so it is open to active superusers only.
    def has_perm(self, perm, obj=None):
        return self.is_active and self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_active and self.is_superuser
