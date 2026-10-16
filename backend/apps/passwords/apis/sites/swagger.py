"""Swagger docs for the sites endpoints, one per view in views.py."""
from drf_spectacular.utils import extend_schema

from apps.base.api.schema import PAGINATION_PARAMETERS, api_response, combine_schemas, error_responses

from .serializers import SiteListQuerySerializer, SiteSerializer, SiteWriteSerializer

TAGS = ['Sites']


site_list = extend_schema(
    operation_id='sites_list',
    tags=TAGS,
    summary='List sites',
    description='Places site passwords are kept for (not carriers), by name. Guarded by the passwords module.',
    parameters=[SiteListQuerySerializer, *PAGINATION_PARAMETERS],
    responses={200: api_response(SiteSerializer, paginated=True), **error_responses(400, 401, 403)},
)


site_create = extend_schema(
    operation_id='sites_create',
    tags=TAGS,
    summary='Create a site',
    description='The name is unique among live sites, whatever its case.',
    request=SiteWriteSerializer,
    responses={201: api_response(SiteSerializer), **error_responses(400, 401, 403)},
)


site_detail = combine_schemas(
    extend_schema(
        methods=['GET'],
        tags=TAGS,
        summary='Get a site',
        responses={200: api_response(SiteSerializer), **error_responses(401, 403, 404)},
    ),
    extend_schema(
        methods=['PATCH'],
        tags=TAGS,
        summary='Update a site',
        description='Name and link; send only what changes.',
        request=SiteWriteSerializer,
        responses={200: api_response(SiteSerializer), **error_responses(400, 401, 403, 404)},
    ),
    extend_schema(
        methods=['DELETE'],
        tags=TAGS,
        summary='Delete a site',
        description='Soft delete. Refused (400, under "site") while live passwords use the site.',
        responses={200: api_response(), **error_responses(400, 401, 403, 404)},
    ),
)
