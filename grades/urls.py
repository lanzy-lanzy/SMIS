from django.urls import path
from . import views

app_name = 'grades'

urlpatterns = [
    path('', views.grade_list, name='grade_list'),
    path('encode/<int:assignment_pk>/', views.grade_encode, name='grade_encode'),
    path('save/<int:assignment_pk>/', views.grade_save, name='grade_save'),
    path('submissions/', views.submission_list, name='submission_list'),
    path('submissions/<int:pk>/validate/', views.submission_validate, name='submission_validate'),
]
