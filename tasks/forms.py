from django import forms
from .models import Task


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title']
        labels = {'title': 'New task'}
        widgets = {
            'title': forms.TextInput(
                attrs={'placeholder': 'What do you need to do?'}
            ),
        }