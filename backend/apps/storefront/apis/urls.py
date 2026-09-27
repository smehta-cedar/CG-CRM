from django.urls import include, path

app_name = 'apis'

urlpatterns = [
    path('storefront/', include('apps.storefront.apis.products.urls')),
]
