from django.urls import include, path

app_name = 'apis'

urlpatterns = [
    path('notifications/', include('apps.notifications.apis.notifications.urls')),
]
