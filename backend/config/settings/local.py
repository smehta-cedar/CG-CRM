from .base import *
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-^bo9hs^a*qqg*=(pqndwq9*izb3s=yx7wsipp=*rkes325pj!t'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Request/SQL profiling (django-silk) - local development only.
# UI at /silk/. https://github.com/jazzband/django-silk

INSTALLED_APPS += ['silk']

# First, so the timing covers every other middleware.
MIDDLEWARE = ['silk.middleware.SilkyMiddleware'] + MIDDLEWARE

# Optional cProfile per request; enable with @silk_profile or this flag.
SILKY_PYTHON_PROFILER = True

# /silk/ is superuser-only. Response bodies (portal passwords, JWTs) are
# never stored; request bodies are already masked by SILKY_SENSITIVE_KEYS.
SILKY_AUTHENTICATION = True
SILKY_AUTHORISATION = True
SILKY_PERMISSIONS = lambda user: user.is_superuser
SILKY_MAX_RESPONSE_BODY_SIZE = 0
LOGIN_URL = '/admin/login/'


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'


# Email: printed in the runserver log instead of sent.
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
