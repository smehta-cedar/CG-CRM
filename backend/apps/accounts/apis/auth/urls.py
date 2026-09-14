from django.urls import path

from . import views

app_name = 'auth'

urlpatterns = [
    path('login/', views.login, name='login'),
    path('refresh/', views.refresh, name='refresh'),
    path('logout/', views.logout, name='logout'),
    path('me/', views.me, name='me'),
    path('change-password/', views.change_password, name='change-password'),
]
