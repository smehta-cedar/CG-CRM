"""
Log formatter for logs/*.log, shared by Django (settings LOGGING) and
gunicorn (config/gunicorn.py). An error reads as a block: a rule, the time,
level and logger, the request that failed, then a rich traceback with the
code around each frame. Free of Django imports so the gunicorn master can
load it before Django is set up.
"""

import io
import logging
import sysconfig

from rich.console import Console
from rich.traceback import Traceback

WIDTH = 120
RULE = '─' * WIDTH

# Frames in installed packages and the standard library shrink to one line;
# only our own code is shown with its source.
LIBRARY_PATHS = [sysconfig.get_paths()['purelib'], sysconfig.get_paths()['stdlib']]


class ReadableFormatter(logging.Formatter):

    def format(self, record):
        lines = [
            f'{self.formatTime(record, "%Y-%m-%d %H:%M:%S")}  {record.levelname}  {record.name}',
            record.getMessage(),
        ]

        # django.request attaches the request that failed.
        request = getattr(record, 'request', None)
        if hasattr(request, 'method'):
            lines.append(f'{request.method} {request.get_full_path()}  user={_username(request)}')

        if record.exc_info:
            lines.append(self.formatException(record.exc_info))

        if record.levelno >= logging.ERROR:
            lines.insert(0, RULE)

        return '\n'.join(lines)

    def formatException(self, exc_info):
        console = Console(file=io.StringIO(), width=WIDTH, no_color=True, record=True)
        # No locals: they would write passwords and tokens into the file.
        console.print(Traceback.from_exception(
            *exc_info, width=WIDTH, extra_lines=2, show_locals=False, suppress=LIBRARY_PATHS,
        ))
        return console.export_text().rstrip()


def _username(request):
    try:
        user = request.user
        return user.get_username() if user.is_authenticated else 'anonymous'
    except Exception:
        return 'unknown'
