from django.urls import include, path

urlpatterns = [
    path('auth/', include('apps.accounts.apis.auth.urls')),
    path('users/', include('apps.accounts.apis.users.urls')),
]
