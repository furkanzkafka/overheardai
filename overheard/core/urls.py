from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('setup/', views.setup, name='setup'),
    path('setup/<int:pk>/review/', views.topic_review, name='topic_review'),
    path('setup/<int:pk>/delete/', views.topic_delete, name='topic_delete'),
    path('setup/<int:pk>/email/', views.topic_email, name='topic_email'),
    path('setup/<int:pk>/scan/', views.topic_scan, name='topic_scan'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/<int:pk>/action/', views.item_action, name='item_action'),
    path('settings/', views.settings_page, name='settings'),
]
