from django.urls import path

from .views import change_password, login, logout, me, refresh

app_name = 'auth'

urlpatterns = [
    path('login/', login, name='login'),
    path('refresh/', refresh, name='refresh'),
    path('logout/', logout, name='logout'),
    path('me/', me, name='me'),
    path('change-password/', change_password, name='change-password'),
]
