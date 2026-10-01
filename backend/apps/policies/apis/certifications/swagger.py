"""Swagger docs for the certification endpoints, one per view in views.py."""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema

from apps.base.api.schema import (
    PAGINATION_PARAMETERS,
    api_response,
    combine_schemas,
    error_responses,
)

from .serializers import (
    CertificationCreateSerializer,
    CertificationListQuerySerializer,
    CertificationNoteSerializer,
    CertificationSerializer,
    CertificationUpdateSerializer,
)

TAGS = ['Certifications']


certification_list = extend_schema(
    operation_id='certifications_list',
    tags=TAGS,
    summary='List certifications',
    description='Sorted by agent name, then due date, carrier name and line of business.',
    parameters=[CertificationListQuerySerializer, *PAGINATION_PARAMETERS],
    responses={200: api_response(CertificationSerializer, paginated=True), **error_responses(400, 401, 403)},
)


certification_create = extend_schema(
    operation_id='certifications_create',
    tags=TAGS,
    summary='Create a certification',
    description=(
        'Only agent is required; nothing else is checked. due_date defaults to the next yearly deadline. '
        'Send multipart form data to attach a PDF (at most 10 MB; anything else is a 400 under file); '
        'uploading does not set is_verified. '
        'Records an "added" note listing every filled field.'
    ),
    request={
        'application/json': CertificationCreateSerializer,
        'multipart/form-data': CertificationCreateSerializer,
    },
    responses={201: api_response(CertificationSerializer), **error_responses(400, 401, 403)},
)


certification_detail = combine_schemas(
    extend_schema(
        methods=['GET'],
        tags=TAGS,
        summary='Get a certification',
        responses={200: api_response(CertificationSerializer), **error_responses(401, 403, 404)},
    ),
    extend_schema(
        methods=['PATCH'],
        tags=TAGS,
        summary='Update a certification',
        description=(
            'Records an "edited" note when something changed. '
            'Send multipart form data with file to replace the PDF; leaving file out keeps it.'
        ),
        request={
            'application/json': CertificationUpdateSerializer,
            'multipart/form-data': CertificationUpdateSerializer,
        },
        responses={200: api_response(CertificationSerializer), **error_responses(400, 401, 403, 404)},
    ),
    extend_schema(
        methods=['DELETE'],
        tags=TAGS,
        summary='Delete a certification',
        description='Soft delete: the certification is hidden.',
        responses={200: api_response(), **error_responses(401, 403, 404)},
    ),
)


certification_notes = extend_schema(
    operation_id='certifications_notes',
    tags=TAGS,
    summary="List a certification's change notes",
    description='Newest first. Not paginated.',
    responses={200: api_response(CertificationNoteSerializer, many=True), **error_responses(401, 403, 404)},
)


certification_file = extend_schema(
    operation_id='certifications_file',
    tags=TAGS,
    summary="Download a certification's PDF",
    description='Sent as an attachment under the name it was uploaded with. 404 when the certification has no file.',
    responses={
        (200, 'application/pdf'): OpenApiResponse(OpenApiTypes.BINARY, description='The PDF.'),
        **error_responses(401, 403, 404),
    },
)
