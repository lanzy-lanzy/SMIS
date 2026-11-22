from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.landing, name='landing'),
    path('dashboard/', views.index, name='index'),
    path('dashboard/achievement/', views.achievement_partial, name='achievement_partial'),
]
