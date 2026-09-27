from django.urls import path

from .views import role_list

app_name = 'roles'

urlpatterns = [
    path('', role_list, name='list'),
]
