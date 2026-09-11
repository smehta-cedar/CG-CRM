from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    """Manager for a User keyed by email instead of username."""

    # The manager is referenced from migrations (e.g. data migrations that
    # create seed accounts), so it has to be serialisable.
    use_in_migrations = True

    def normalize_email(self, email):
        """Lowercase the whole address, not just the domain.

        Django only normalises the domain part. Mailboxes we care about are
        case-insensitive in practice, and storing a single canonical form is
        what keeps the unique constraint honest.
        """
        return super().normalize_email(email or '').lower()

    def get_by_natural_key(self, username):
        # Belt and braces: rows written before this manager existed, or by a
        # raw fixture, may not be lowercased.
        return self.get(**{f'{self.model.USERNAME_FIELD}__iexact': username})

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('Users must have an email address.')

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        # set_password(None) stores an unusable password, which is what we
        # want for SSO accounts that never authenticate locally.
        user.set_password(password)
        user.full_clean(exclude=['password'])
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        # A superuser created from the command line has just chosen its own
        # password, so don't force a rotation on first login.
        extra_fields.setdefault('must_change_password', False)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)
