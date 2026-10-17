"""
gunicorn settings for prod (sh/prod.sh). Only warnings and errors are kept,
in logs/gunicorn-error.log, rotated at 5 MB with 5 old files. No access log.
Errors also go, unformatted and never rotated, to logs/error-raw.log.
"""

import os

bind = '0.0.0.0:8000'
workers = int(os.environ.get('GUNICORN_WORKERS', 3))

logconfig_dict = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'readable': {'()': 'config.log_format.ReadableFormatter'},
        'raw': {'format': '%(asctime)s %(levelname)s %(name)s [pid %(process)d] %(message)s'},
    },
    'handlers': {
        'error_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/gunicorn-error.log',
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'readable',
            'encoding': 'utf-8',
        },
        'raw_file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': 'logs/error-raw.log',
            'formatter': 'raw',
            'encoding': 'utf-8',
        },
    },
    # gunicorn's default root points at its console handler, replaced above.
    'root': {'handlers': ['error_file', 'raw_file'], 'level': 'WARNING'},
    'loggers': {
        'gunicorn.error': {'handlers': ['error_file', 'raw_file'], 'level': 'WARNING', 'propagate': False},
        # Each request is logged at INFO, so this drops them all.
        'gunicorn.access': {'handlers': [], 'level': 'WARNING', 'propagate': False},
    },
}
