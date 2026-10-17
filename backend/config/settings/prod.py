from decouple import Csv, config

from .base import *

SECRET_KEY = config('SECRET_KEY')

DEBUG = False

# Comma-separated, e.g. api.example.com,10.0.0.5
ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv())

# Full origins the admin is opened from, e.g. https://api.example.com
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', cast=Csv(), default='')


# HTTPS is ended at the proxy in front of gunicorn, which says so in
# X-Forwarded-Proto. Cookies are only sent back over HTTPS.

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True


# Database: the database is AWS RDS, which refuses unencrypted connections.
# verify-full also checks the server's certificate against Amazon's RDS CA
# bundle (put in the image by the Dockerfile), so nothing can pose as the
# database.

DATABASES['default']['OPTIONS'] = {
    **DATABASES['default'].get('OPTIONS', {}),
    'sslmode': config('DB_SSLMODE', default='verify-full'),
    'sslrootcert': '/etc/ssl/certs/rds-global-bundle.pem',
}

# Each gunicorn worker keeps its connection between requests instead of
# opening one per request, and replaces it if the server closed it.
DATABASES['default']['CONN_MAX_AGE'] = 60
DATABASES['default']['CONN_HEALTH_CHECKS'] = True


# Static files (admin, Swagger UI): sh/prod.sh collects them into
# staticfiles/ and WhiteNoise serves them from gunicorn.
# https://whitenoise.readthedocs.io/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MIDDLEWARE.insert(
    MIDDLEWARE.index('django.middleware.security.SecurityMiddleware') + 1,
    'whitenoise.middleware.WhiteNoiseMiddleware',
)

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}


# Email: agents' sign-in codes go out over SMTP.

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_PORT = config('EMAIL_PORT', cast=int, default=587)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', cast=bool, default=True)
