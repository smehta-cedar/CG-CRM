from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated

from apps.base.api.authentication import TokenlessAuthentication
from apps.base.api.pagination import paginate
from apps.base.api.permissions import module_permission
from apps.base.api.response import APIResponse
from apps.storefront.models import Product, ProductNote
from apps.storefront.utils import (
    diff_snapshots,
    filter_products,
    get_product_or_404,
    normalize_name,
    record_note,
    save_product,
    search_products,
    snapshot,
)
from apps.storefront.validators import ensure_name_free, ensure_options

from . import swagger
from .serializers import (
    ProductCreateSerializer,
    ProductListQuerySerializer,
    ProductNoteSerializer,
    ProductSerializer,
    ProductUpdateSerializer,
)

CAN_MANAGE_STOREFRONT = module_permission('storefront')


@swagger.catalog
@api_view(['GET'])
@authentication_classes([TokenlessAuthentication])
@permission_classes([AllowAny])
def catalog(request):
    """What the public shop lists: every active product, no sign-in needed."""
    products = Product.objects.filter(is_active=True)
    return APIResponse(ProductSerializer(products, many=True).data, 'Catalog fetched successfully.')


@swagger.product_list
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_STOREFRONT])
def product_list(request):
    query = ProductListQuerySerializer(data=request.query_params.dict())
    query.is_valid(raise_exception=True)
    filters = query.validated_data

    products = Product.objects.all()
    search = filters.get('search')
    if search:
        products = search_products(products, search)
    products = filter_products(
        products,
        is_active=filters.get('is_active'),
        category=filters.get('category'),
        product_type=filters.get('product_type'),
    )

    page, meta = paginate(request, products)
    return APIResponse(ProductSerializer(page, many=True).data, 'Products fetched successfully.', meta=meta)


@swagger.product_create
@api_view(['POST'])
@permission_classes([IsAuthenticated, CAN_MANAGE_STOREFRONT])
def product_create(request):
    serializer = ProductCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    name = normalize_name(data['name'])
    ensure_name_free(name)
    ensure_options(data['colors'], data['sizes'])

    with transaction.atomic():
        product = Product.objects.create(
            name=name,
            description=data.get('description', '').strip(),
            category=data.get('category', ''),
            product_type=data.get('product_type', ''),
            image_url=data.get('image_url', '').strip(),
            price=data['price'],
            colors=data['colors'],
            sizes=data['sizes'],
            max_quantity=data.get('max_quantity', 10),
            is_active=data.get('is_active', True),
            created_by=request.user,
            updated_by=request.user,
        )
        record_note(product, request.user, ProductNote.KIND_ADDED, diff_snapshots({}, snapshot(product)))
    return APIResponse(ProductSerializer(product).data, 'Product created successfully.', status=status.HTTP_201_CREATED)


@swagger.product_detail
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, CAN_MANAGE_STOREFRONT])
def product_detail(request, pk):
    product = get_product_or_404(pk)

    if request.method == 'GET':
        return APIResponse(ProductSerializer(product).data, 'Product fetched successfully.')

    if request.method == 'PATCH':
        serializer = ProductUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields = dict(serializer.validated_data)

        if 'name' in fields:
            fields['name'] = normalize_name(fields['name'])
            if fields['name'].lower() != product.name.lower():
                ensure_name_free(fields['name'], exclude=product)
        if 'description' in fields:
            fields['description'] = fields['description'].strip()
        if 'image_url' in fields:
            fields['image_url'] = fields['image_url'].strip()
        ensure_options(fields.get('colors', product.colors), fields.get('sizes', product.sizes))

        before = snapshot(product)
        with transaction.atomic():
            save_product(product, request.user, **fields)
            record_note(product, request.user, ProductNote.KIND_EDITED, diff_snapshots(before, snapshot(product)))
        return APIResponse(ProductSerializer(product).data, 'Product updated successfully.')

    # DELETE: soft delete; the name becomes free for reuse. Past orders keep their link.
    product.delete(user=request.user)
    return APIResponse(None, 'Product deleted successfully.')


@swagger.product_notes
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_STOREFRONT])
def product_notes(request, pk):
    product = get_product_or_404(pk)
    notes = product.notes.select_related('created_by')
    return APIResponse(ProductNoteSerializer(notes, many=True).data, 'Product notes fetched successfully.')
