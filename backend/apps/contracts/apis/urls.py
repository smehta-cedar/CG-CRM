from django.urls import include, path

app_name = 'apis'

urlpatterns = [
    path('contracts/', include('apps.contracts.apis.contracts.urls')),
]
