from django.urls import include, path

app_name = 'agency'

urlpatterns = [
    path('', include('apps.agency.apis.urls')),
]
