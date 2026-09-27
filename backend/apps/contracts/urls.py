from django.urls import include, path

app_name = 'contracts'

urlpatterns = [
    path('', include('apps.contracts.apis.urls')),
]
