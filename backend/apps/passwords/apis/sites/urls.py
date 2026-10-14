from django.urls import path

from .views import site_create, site_detail, site_list

app_name = 'sites'

urlpatterns = [
    path('', site_list, name='list'),
    path('create/', site_create, name='create'),
    path('<uuid:pk>/', site_detail, name='detail'),
]
