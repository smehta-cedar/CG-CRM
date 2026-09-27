from django.urls import path

from .views import (
    certification_create,
    certification_detail,
    certification_file,
    certification_list,
    certification_notes,
)

app_name = 'certifications'

urlpatterns = [
    path('', certification_list, name='list'),
    path('create/', certification_create, name='create'),
    path('<uuid:pk>/', certification_detail, name='detail'),
    path('<uuid:pk>/notes/', certification_notes, name='notes'),
    path('<uuid:pk>/file/', certification_file, name='file'),
]
