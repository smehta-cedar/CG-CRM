from django.urls import include, path

app_name = 'agents'

urlpatterns = [
    path('', include('apps.agents.apis.urls')),
]
