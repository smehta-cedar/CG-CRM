from django.urls import include, path

app_name = 'notifications'

urlpatterns = [
    path('', include('apps.notifications.apis.urls')),
]
