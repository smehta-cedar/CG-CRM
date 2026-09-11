from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PermissionTreeView, RoleViewSet

router = DefaultRouter()
router.register('roles', RoleViewSet, basename='role')

urlpatterns = [
    path('permissions/', PermissionTreeView.as_view(), name='permission-tree'),
    path('', include(router.urls)),
]
