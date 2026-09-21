"""Swagger helpers, so the docs show the envelope and not the bare serializer.

Each API folder keeps its docs in swagger.py and views.py applies them:

    # swagger.py
    user_detail = combine_schemas(
        extend_schema(methods=['GET'], responses={200: api_response(UserSerializer)}),
        extend_schema(methods=['PATCH'], request=UserUpdateSerializer, responses={200: api_response(UserSerializer)}),
    )

    # views.py
    @swagger.user_detail
    @api_view(['GET', 'PATCH'])
    def user_detail(request, pk): ...
"""
from drf_spectacular.utils import OpenApiParameter, inline_serializer
from rest_framework import serializers

PAGINATION_PARAMETERS = [
    OpenApiParameter('page', int, description='Page number, starting at 1.'),
    OpenApiParameter('page_size', int, description='Items per page (default 20, max 100).'),
]


class PaginationMetaSerializer(serializers.Serializer):
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    total_pages = serializers.IntegerField()
    total_items = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)


class ErrorResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=False)
    message = serializers.CharField()
    code = serializers.CharField()
    errors = serializers.DictField(allow_null=True)


# One component per name; spectacular warns if two classes share a name.
_envelopes = {}


def api_response(serializer_class=None, *, paginated=False):
    stem = serializer_class.__name__.removesuffix('Serializer') if serializer_class else 'Empty'
    name = f'{stem}PageResponse' if paginated else f'{stem}Response'

    if name not in _envelopes:
        fields = {
            'success': serializers.BooleanField(),
            'message': serializers.CharField(),
        }
        if serializer_class is None:
            fields['data'] = serializers.JSONField(allow_null=True)
        elif paginated:
            fields['data'] = serializer_class(many=True)
            fields['meta'] = PaginationMetaSerializer()
        else:
            fields['data'] = serializer_class()
        _envelopes[name] = inline_serializer(name=name, fields=fields)

    return _envelopes[name]


def error_responses(*status_codes):
    return {code: ErrorResponseSerializer for code in status_codes}


def combine_schemas(*decorators):
    """Merge several extend_schema(methods=[...]) into one decorator, for a
    view that serves more than one HTTP method."""

    def decorate(view):
        for decorator in reversed(decorators):
            view = decorator(view)
        return view

    return decorate
