from django.urls import path

from .views import agency_create, agency_detail, agency_list

app_name = 'agencies'

urlpatterns = [
    path('', agency_list, name='list'),
    path('create/', agency_create, name='create'),
    path('<uuid:pk>/', agency_detail, name='detail'),
]
