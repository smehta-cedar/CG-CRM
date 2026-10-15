from django.urls import path

from .views import (
    agency_comment_delete,
    agency_comments,
    agency_create,
    agency_detail,
    agency_list,
    agency_notes,
)

app_name = 'agencies'

urlpatterns = [
    path('', agency_list, name='list'),
    path('create/', agency_create, name='create'),
    path('<uuid:pk>/', agency_detail, name='detail'),
    path('<uuid:pk>/notes/', agency_notes, name='notes'),
    path('<uuid:pk>/comments/', agency_comments, name='comments'),
    path('comments/<uuid:pk>/', agency_comment_delete, name='comment-delete'),
]
