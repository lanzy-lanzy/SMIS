from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.reports_index, name='index'),
    path('grade-trends/', views.grade_trends, name='grade_trends'),
    path('section-performance/', views.section_performance, name='section_performance'),
    path('subject-performance/', views.subject_performance, name='subject_performance'),
    path('at-risk-students/', views.at_risk_students, name='at_risk_students'),
    path('student-history/<int:student_pk>/', views.student_history, name='student_history'),
]
