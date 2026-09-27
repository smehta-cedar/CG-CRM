from django.urls import path

from .views import policy_type_create, policy_type_detail, policy_type_list, policy_type_notes

app_name = 'policy_types'

urlpatterns = [
    path('', policy_type_list, name='list'),
    path('create/', policy_type_create, name='create'),
    path('<uuid:pk>/', policy_type_detail, name='detail'),
    path('<uuid:pk>/notes/', policy_type_notes, name='notes'),
]
