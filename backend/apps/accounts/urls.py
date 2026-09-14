from django.urls import include, path

urlpatterns = [
    path('', include('apps.accounts.apis.urls')),
]
