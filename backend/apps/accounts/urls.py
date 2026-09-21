from django.urls import include, path

app_name = 'accounts'

urlpatterns = [
    path('', include('apps.accounts.apis.urls')),
]
