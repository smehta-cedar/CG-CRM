from django.urls import path

from .views import contract_create, contract_detail, contract_list, contract_notes, contract_notes_all

app_name = 'contracts'

urlpatterns = [
    path('', contract_list, name='list'),
    path('create/', contract_create, name='create'),
    path('notes/', contract_notes_all, name='notes-all'),
    path('<uuid:pk>/', contract_detail, name='detail'),
    path('<uuid:pk>/notes/', contract_notes, name='notes'),
]
