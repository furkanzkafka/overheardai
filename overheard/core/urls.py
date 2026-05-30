from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('setup/', views.setup, name='setup'),
    path('setup/<int:pk>/edit/', views.topic_edit, name='topic_edit'),
    path('setup/<int:pk>/delete/', views.topic_delete, name='topic_delete'),
    path('setup/schedule/', views.schedule_save, name='schedule_save'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/<int:pk>/action/', views.item_action, name='item_action'),
]
