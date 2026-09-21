from django.urls import path

from .views import (
    user_block,
    user_create,
    user_detail,
    user_list,
    user_set_password,
    user_unblock,
)

app_name = 'users'

urlpatterns = [
    path('', user_list, name='list'),
    path('create/', user_create, name='create'),
    path('<uuid:pk>/', user_detail, name='detail'),
    path('<uuid:pk>/block/', user_block, name='block'),
    path('<uuid:pk>/unblock/', user_unblock, name='unblock'),
    path('<uuid:pk>/set-password/', user_set_password, name='set-password'),
]
