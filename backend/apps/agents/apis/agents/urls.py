from django.urls import path

from .views import agent_create, agent_detail, agent_list, agent_notes

app_name = 'agents'

urlpatterns = [
    path('', agent_list, name='list'),
    path('create/', agent_create, name='create'),
    path('<uuid:pk>/', agent_detail, name='detail'),
    path('<uuid:pk>/notes/', agent_notes, name='notes'),
]
