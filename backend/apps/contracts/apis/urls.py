from django.urls import include, path

app_name = 'apis'

urlpatterns = [
    path('contracts/', include('apps.contracts.apis.contracts.urls')),
    path('agency-contracts/', include('apps.contracts.apis.agency_contracts.urls')),
]
