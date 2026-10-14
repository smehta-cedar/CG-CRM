from django.urls import path

from .views import request_create, request_detail, request_list, request_merch_create, request_mine

app_name = 'requests'

urlpatterns = [
    path('', request_list, name='list'),
    path('create/', request_create, name='create'),
    path('mine/', request_mine, name='mine'),
    path('merch/', request_merch_create, name='merch'),
    path('<uuid:pk>/', request_detail, name='detail'),
]
