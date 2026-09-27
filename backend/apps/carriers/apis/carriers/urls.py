from django.urls import path

from .views import carrier_create, carrier_detail, carrier_list, carrier_notes

app_name = 'carriers'

urlpatterns = [
    path('', carrier_list, name='list'),
    path('create/', carrier_create, name='create'),
    path('<uuid:pk>/', carrier_detail, name='detail'),
    path('<uuid:pk>/notes/', carrier_notes, name='notes'),
]
