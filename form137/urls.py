from django.urls import path
from . import views

app_name = 'form137'

urlpatterns = [
    path('', views.form137_list, name='form137_list'),
    path('generate/<int:student_pk>/<int:sy_pk>/', views.form137_generate, name='form137_generate'),
    path('<int:record_pk>/preview/', views.form137_preview, name='form137_preview'),
    path('bulk-generate/', views.form137_bulk_generate, name='form137_bulk_generate'),
    path('export/', views.form137_export, name='form137_export'),
]
