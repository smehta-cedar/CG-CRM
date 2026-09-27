from django.urls import include, path

app_name = 'storefront'

urlpatterns = [
    path('', include('apps.storefront.apis.urls')),
]
