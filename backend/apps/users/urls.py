from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ChangeOwnPasswordView, LoginView, UserViewSet

router = DefaultRouter()
router.register('users', UserViewSet, basename='user')

auth_urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('change-password/', ChangeOwnPasswordView.as_view(), name='change-password'),
]

urlpatterns = [
    path('auth/', include(auth_urlpatterns)),
    path('', include(router.urls)),
]
