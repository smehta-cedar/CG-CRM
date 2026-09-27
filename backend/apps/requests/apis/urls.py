from django.urls import include, path

app_name = 'apis'

urlpatterns = [
    path('requests/', include('apps.requests.apis.requests.urls')),
]
