from django.urls import path

from .views import password_create, password_detail, password_list, password_notes

app_name = 'passwords'

urlpatterns = [
    path('', password_list, name='list'),
    path('create/', password_create, name='create'),
    path('<uuid:pk>/', password_detail, name='detail'),
    path('<uuid:pk>/notes/', password_notes, name='notes'),
]
