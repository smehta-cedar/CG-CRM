from django.urls import path

from .views import notification_list, notification_read, notification_read_all

app_name = 'notifications'

urlpatterns = [
    path('', notification_list, name='list'),
    path('read-all/', notification_read_all, name='read-all'),
    path('<uuid:pk>/read/', notification_read, name='read'),
]
