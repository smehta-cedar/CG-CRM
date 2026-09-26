from django.urls import include, path

app_name = 'apis'

urlpatterns = [
    path('agencies/', include('apps.agency.apis.agencies.urls')),
]
