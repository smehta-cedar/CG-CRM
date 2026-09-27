from django.urls import include, path

app_name = 'apis'

urlpatterns = [
    path('carriers/', include('apps.carriers.apis.carriers.urls')),
]
