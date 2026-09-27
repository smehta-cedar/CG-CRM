"""Swagger docs for the storefront endpoints, one per view in views.py."""
from drf_spectacular.utils import extend_schema

from apps.base.api.schema import (
    PAGINATION_PARAMETERS,
    api_response,
    combine_schemas,
    error_responses,
)

from .serializers import (
    ProductCreateSerializer,
    ProductListQuerySerializer,
    ProductNoteSerializer,
    ProductSerializer,
    ProductUpdateSerializer,
)

TAGS = ['Storefront']


catalog = extend_schema(
    operation_id='storefront_catalog',
    tags=TAGS,
    summary='The public catalog',
    description='Every active product, for the shop page. No sign-in needed. Not paginated.',
    auth=[],
    responses={200: api_response(ProductSerializer, many=True)},
)


product_list = extend_schema(
    operation_id='storefront_products_list',
    tags=TAGS,
    summary='List products',
    parameters=[ProductListQuerySerializer, *PAGINATION_PARAMETERS],
    responses={200: api_response(ProductSerializer, paginated=True), **error_responses(400, 401, 403)},
)


product_create = extend_schema(
    operation_id='storefront_products_create',
    tags=TAGS,
    summary='Create a product',
    description='Needs at least one colour and one size. Records an "added" note.',
    request=ProductCreateSerializer,
    responses={201: api_response(ProductSerializer), **error_responses(400, 401, 403)},
)


product_detail = combine_schemas(
    extend_schema(
        methods=['GET'],
        tags=TAGS,
        summary='Get a product',
        responses={200: api_response(ProductSerializer), **error_responses(401, 403, 404)},
    ),
    extend_schema(
        methods=['PATCH'],
        tags=TAGS,
        summary='Update a product',
        description='Records an "edited" note when something changed.',
        request=ProductUpdateSerializer,
        responses={200: api_response(ProductSerializer), **error_responses(400, 401, 403, 404)},
    ),
    extend_schema(
        methods=['DELETE'],
        tags=TAGS,
        summary='Delete a product',
        description='Soft delete: the product leaves the shop; past orders keep their link.',
        responses={200: api_response(), **error_responses(401, 403, 404)},
    ),
)


product_notes = extend_schema(
    operation_id='storefront_products_notes',
    tags=TAGS,
    summary="List a product's change notes",
    description='Newest first. Not paginated.',
    responses={200: api_response(ProductNoteSerializer, many=True), **error_responses(401, 403, 404)},
)
