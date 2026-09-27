from django.urls import include, path

app_name = 'requests'

urlpatterns = [
    path('', include('apps.requests.apis.urls')),
]
