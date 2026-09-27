from django.urls import include, path

app_name = 'apis'

urlpatterns = [
    path('passwords/', include('apps.passwords.apis.passwords.urls')),
]
