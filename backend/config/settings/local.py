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


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'