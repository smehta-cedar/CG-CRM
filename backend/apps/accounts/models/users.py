from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils.functional import cached_property

from apps.base.managers import SoftDeleteManager
from apps.base.models import BaseModel

from .designations import Designation
from .roles import ACTIONS, AGENT_ROLE_NAME, PERMISSION_LABELS, Role, RolePermission


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
    """Logs in with email. Access comes from `roles`, not Django permissions.

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
    # Any number of roles; what they grant adds up. None means no access.
    roles = models.ManyToManyField(Role, blank=True, related_name='users')

    # Set for an agent who signs in with a work email and a code. Staff accounts leave it empty.
    agent = models.OneToOneField(
        'agents.Agent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user',
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
        """{"dashboard": {"view": True, ...}, ...} from the roles.

        Each action is allowed when any of the roles allows it. Cached on
        this instance. No roles grant nothing, nor does an inactive or
        soft-deleted one. An agent's account uses the role named
        AGENT_ROLE_NAME, not its own.
        """
        roles = Role.objects.filter(name__iexact=AGENT_ROLE_NAME) if self.agent_id else self.roles.all()
        # The default managers already skip soft-deleted roles and permission rows.
        permissions = RolePermission.objects.filter(role__in=roles.filter(is_active=True))
        granted = {}
        for permission in permissions:
            flags = granted.setdefault(permission.module, dict.fromkeys(ACTIONS, False))
            for action in ACTIONS:
                flags[action] = flags[action] or getattr(permission, f'can_{action}')
        return granted

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
        # An agent's account sees only its own record, whatever the role grants.
        if self.agent_id and not module.startswith('agent_view.'):
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
