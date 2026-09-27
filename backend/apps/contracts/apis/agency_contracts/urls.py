from django.urls import path

from .views import (
    agency_contract_create,
    agency_contract_detail,
    agency_contract_list,
    agency_contract_notes,
)

app_name = 'agency_contracts'

urlpatterns = [
    path('', agency_contract_list, name='list'),
    path('create/', agency_contract_create, name='create'),
    path('<uuid:pk>/', agency_contract_detail, name='detail'),
    path('<uuid:pk>/notes/', agency_contract_notes, name='notes'),
]
