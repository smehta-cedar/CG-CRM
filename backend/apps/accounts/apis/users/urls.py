from django.urls import path

from . import views

app_name = 'users'

urlpatterns = [
    path('', views.user_list_create, name='list'),
    path('<uuid:pk>/', views.user_detail, name='detail'),
    path('<uuid:pk>/block/', views.user_block, name='block'),
    path('<uuid:pk>/unblock/', views.user_unblock, name='unblock'),
    path('<uuid:pk>/set-password/', views.user_set_password, name='set-password'),
]
