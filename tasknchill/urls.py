from django.contrib import admin
from django.urls import path

from tasks.views import delete_task, task_list, toggle_task

urlpatterns = [
    path('', task_list, name='task_list'),
    path('tasks/<int:task_id>/toggle/', toggle_task, name='toggle_task'),
    path('tasks/<int:task_id>/delete/', delete_task, name='delete_task'),
    path('admin/', admin.site.urls),
]