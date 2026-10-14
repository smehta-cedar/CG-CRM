from django.db.models import Count, Q
from django.db.models.functions import Lower
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.base.api.pagination import paginate
from apps.base.api.permissions import module_permission
from apps.base.api.response import APIResponse
from apps.passwords.models import Site
from apps.passwords.utils import get_site_or_404
from apps.passwords.validators import ensure_site_name_free, ensure_site_unused

from . import swagger
from .serializers import SiteListQuerySerializer, SiteSerializer, SiteWriteSerializer

# Sites are part of the Passwords module: the same permission guards them.
CAN_MANAGE_PASSWORDS = module_permission('passwords')


def with_password_count(sites):
    return sites.annotate(
        password_count=Count('passwords', filter=Q(passwords__deleted_at__isnull=True), distinct=True)
    )


def site_data(site):
    return SiteSerializer(with_password_count(Site.objects.filter(pk=site.pk)).get()).data


@swagger.site_list
@api_view(['GET'])
@permission_classes([IsAuthenticated, CAN_MANAGE_PASSWORDS])
def site_list(request):
    query = SiteListQuerySerializer(data=request.query_params.dict())
    query.is_valid(raise_exception=True)

    sites = with_password_count(Site.objects.all())
    search = query.validated_data.get('search')
    if search:
        sites = sites.filter(name__icontains=search)

    page, meta = paginate(request, sites.order_by(Lower('name')))
    return APIResponse(SiteSerializer(page, many=True).data, 'Sites fetched successfully.', meta=meta)


@swagger.site_create
@api_view(['POST'])
@permission_classes([IsAuthenticated, CAN_MANAGE_PASSWORDS])
def site_create(request):
    serializer = SiteWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    name = serializer.validated_data['name']
    ensure_site_name_free(name)
    site = Site.objects.create(
        name=name,
        link=serializer.validated_data.get('link', ''),
        created_by=request.user,
        updated_by=request.user,
    )
    return APIResponse(site_data(site), 'Site created successfully.', status=status.HTTP_201_CREATED)


@swagger.site_detail
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, CAN_MANAGE_PASSWORDS])
def site_detail(request, pk):
    site = get_site_or_404(pk)

    if request.method == 'GET':
        return APIResponse(site_data(site), 'Site fetched successfully.')

    if request.method == 'PATCH':
        serializer = SiteWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        changed = {}
        name = serializer.validated_data.get('name')
        if name is not None and name.strip() != site.name:
            ensure_site_name_free(name, exclude=site)
            changed['name'] = name
        if 'link' in serializer.validated_data:
            changed['link'] = serializer.validated_data['link']
        if changed:
            for field, value in changed.items():
                setattr(site, field, value)
            site.updated_by = request.user
            site.save(update_fields=[*changed, 'updated_by'])
        return APIResponse(site_data(site), 'Site updated successfully.')

    # DELETE: soft delete, only once no live password uses the site.
    ensure_site_unused(site)
    site.delete(user=request.user)
    return APIResponse(None, 'Site deleted successfully.')
