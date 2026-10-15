from django.urls import path

from .views import task_create, task_detail, task_list

app_name = 'tasks'

urlpatterns = [
    path('', task_list, name='list'),
    path('create/', task_create, name='create'),
    path('<uuid:pk>/', task_detail, name='detail'),
]
