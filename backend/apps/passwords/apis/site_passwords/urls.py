from django.urls import path

from .views import site_password_create, site_password_detail, site_password_list, site_password_notes

app_name = 'site_passwords'

urlpatterns = [
    path('', site_password_list, name='list'),
    path('create/', site_password_create, name='create'),
    path('<uuid:pk>/', site_password_detail, name='detail'),
    path('<uuid:pk>/notes/', site_password_notes, name='notes'),
]
