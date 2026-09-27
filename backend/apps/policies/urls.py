from django.urls import include, path

app_name = 'policies'

urlpatterns = [
    path('', include('apps.policies.apis.urls')),
]
