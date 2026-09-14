import logging

from django.conf import settings
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .response import error_body

logger = logging.getLogger(__name__)


def exception_handler(exc, context):
    """Turn every API error into the error envelope (see response.error_body).

    Services and selectors raise plain Django exceptions so they stay free of
    DRF; they are translated here:

        ValidationError   -> 400, field errors under "errors"
        PermissionDenied  -> 403, with the service's message
        Http404           -> 404
    """
    exc = _to_drf_exception(exc)
    response = drf_exception_handler(exc, context)

    if response is None:
        if settings.DEBUG:
            return None  # let Django render the traceback page
        logger.exception('Unhandled API error', exc_info=exc)
        return Response(
            error_body('Something went wrong. Please try again later.', 'server_error'),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    response.data = _error_body_for(exc)
    return response


def _to_drf_exception(exc):
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, 'error_dict'):
            errors = dict(exc.message_dict)
            if '__all__' in errors:
                errors['non_field_errors'] = errors.pop('__all__')
            return exceptions.ValidationError(errors)
        return exceptions.ValidationError({'non_field_errors': exc.messages})
    if isinstance(exc, DjangoPermissionDenied):
        return exceptions.PermissionDenied(str(exc) or None)
    if isinstance(exc, Http404):
        return exceptions.NotFound(str(exc) or None)
    return exc


def _error_body_for(exc):
    detail = exc.detail

    if isinstance(exc, exceptions.ValidationError):
        errors = detail if isinstance(detail, dict) else {'non_field_errors': detail}
        non_field = errors.get('non_field_errors')
        message = str(non_field[0]) if non_field else 'Invalid input.'
        return error_body(message, 'invalid', errors)

    # SimpleJWT raises with a dict: {"detail": ..., "code": ..., "messages": [...]}
    if isinstance(detail, dict):
        message = str(detail.get('detail', exc.default_detail))
        code = detail.get('code') or exc.default_code
    elif isinstance(detail, list):
        message = str(detail[0]) if detail else str(exc.default_detail)
        code = getattr(detail[0], 'code', None) if detail else None
    else:
        message = str(detail)
        code = getattr(detail, 'code', None)

    return error_body(message, str(code or exc.default_code))
