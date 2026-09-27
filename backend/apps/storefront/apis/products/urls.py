from django.urls import path

from .views import catalog, product_create, product_detail, product_list, product_notes

app_name = 'products'

urlpatterns = [
    path('catalog/', catalog, name='catalog'),
    path('products/', product_list, name='list'),
    path('products/create/', product_create, name='create'),
    path('products/<uuid:pk>/', product_detail, name='detail'),
    path('products/<uuid:pk>/notes/', product_notes, name='notes'),
]
