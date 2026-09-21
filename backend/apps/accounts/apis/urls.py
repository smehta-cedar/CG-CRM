from django.urls import include, path

app_name = 'apis'

urlpatterns = [
    path('auth/', include('apps.accounts.apis.auth.urls')),
    path('users/', include('apps.accounts.apis.users.urls')),
]
