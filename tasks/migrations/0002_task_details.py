from django.db import migrations, models


def copy_completion(apps, schema_editor):
    Task = apps.get_model('tasks', 'Task')
    tasks = Task.objects.using(schema_editor.connection.alias)
    tasks.filter(completed=True).update(status='completed')


def restore_completion(apps, schema_editor):
    Task = apps.get_model('tasks', 'Task')
    tasks = Task.objects.using(schema_editor.connection.alias)
    tasks.filter(status='completed').update(completed=True)


class Migration(migrations.Migration):
    dependencies = [('tasks', '0001_initial')]

    operations = [
        migrations.AddField(model_name='task', name='description', field=models.TextField(blank=True)),
        migrations.AddField(model_name='task', name='category', field=models.CharField(blank=True, choices=[('work', 'Work'), ('school', 'School'), ('home', 'Home')], max_length=10)),
        migrations.AddField(model_name='task', name='priority', field=models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], default='medium', max_length=10)),
        migrations.AddField(model_name='task', name='status', field=models.CharField(choices=[('pending', 'Pending'), ('started', 'Started'), ('completed', 'Completed')], default='pending', max_length=10)),
        migrations.RunPython(copy_completion, restore_completion),
        migrations.RemoveField(model_name='task', name='completed'),
    ]
