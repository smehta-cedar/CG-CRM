from django.urls import include, path

app_name = 'passwords'

urlpatterns = [
    path('', include('apps.passwords.apis.urls')),
]
