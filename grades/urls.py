from django.urls import path
from . import views

app_name = 'grades'

urlpatterns = [
    path('', views.grade_list, name='grade_list'),
    path('encode/<int:assignment_pk>/', views.grade_encode, name='grade_encode'),
    path('save/<int:assignment_pk>/', views.grade_save, name='grade_save'),
    path('encode-select/', views.grade_encode_select, name='grade_encode_select'),
    path('encode-all/', views.grade_encode_all, name='grade_encode_all'),
    path('save-all/', views.grade_save_all, name='grade_save_all'),
    path('submissions/', views.submission_list, name='submission_list'),
    path('submissions/<int:pk>/validate/', views.submission_validate, name='submission_validate'),
    path('export/', views.grade_export, name='grade_export'),
    path('encode-modal/', views.encode_modal, name='encode_modal'),
]
