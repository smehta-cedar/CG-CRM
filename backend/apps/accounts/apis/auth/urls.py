from django.urls import path

from .views import agent_code, agent_home, agent_login, change_password, login, logout, me, refresh

app_name = 'auth'

urlpatterns = [
    path('login/', login, name='login'),
    path('agent-code/', agent_code, name='agent-code'),
    path('agent-login/', agent_login, name='agent-login'),
    path('agent/', agent_home, name='agent'),
    path('refresh/', refresh, name='refresh'),
    path('logout/', logout, name='logout'),
    path('me/', me, name='me'),
    path('change-password/', change_password, name='change-password'),
]
