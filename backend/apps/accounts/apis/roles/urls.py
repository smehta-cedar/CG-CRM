from django.urls import path

from .views import role_create, role_detail, role_list, role_modules

app_name = 'roles'

urlpatterns = [
    path('', role_list, name='list'),
    path('modules/', role_modules, name='modules'),
    path('create/', role_create, name='create'),
    path('<uuid:pk>/', role_detail, name='detail'),
]
