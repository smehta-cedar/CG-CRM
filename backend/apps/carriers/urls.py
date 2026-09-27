from django.urls import include, path

app_name = 'carriers'

urlpatterns = [
    path('', include('apps.carriers.apis.urls')),
]
