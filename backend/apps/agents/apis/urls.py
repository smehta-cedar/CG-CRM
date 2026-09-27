from django.urls import include, path

app_name = 'apis'

urlpatterns = [
    path('agents/', include('apps.agents.apis.agents.urls')),
]
