from django.urls import path

from .views import (
    carrier_policy_create,
    carrier_policy_detail,
    carrier_policy_list,
    carrier_policy_notes,
)

app_name = 'carrier_policies'

urlpatterns = [
    path('', carrier_policy_list, name='list'),
    path('create/', carrier_policy_create, name='create'),
    path('<uuid:pk>/', carrier_policy_detail, name='detail'),
    path('<uuid:pk>/notes/', carrier_policy_notes, name='notes'),
]
