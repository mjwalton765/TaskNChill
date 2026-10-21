from django.contrib import admin
from django.urls import path

from tasks import views

urlpatterns = [
    path('', views.task_list, name='task_list'),
    path('tasks/add/', views.add_task, name='add_task'),
    path('tasks/find/', views.find_tasks, name='find_tasks'),
    path('tasks/results/', views.search_results, name='search_results'),
    path('tasks/<int:task_id>/edit/', views.edit_task, name='edit_task'),
    path('tasks/completed/', views.completed_tasks, name='completed_tasks'),
    path('tasks/deleted/', views.deleted_tasks, name='deleted_tasks'),
    path('tasks/action/', views.task_action, name='task_action'),
    path('tasks/history/', views.task_history, name='task_history'),
    path('tasks/history/delete/', views.delete_history, name='delete_history'),
    path('admin/', admin.site.urls),
]
