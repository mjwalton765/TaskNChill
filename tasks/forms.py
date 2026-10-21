from django import forms

from .models import Task


class TaskForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            del self.fields['status']

    class Meta:
        model = Task
        fields = ['title', 'description', 'category', 'priority', 'status']
        labels = {'title': 'Task name'}
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'What do you need to do?'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class TaskFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        label='Search',
        max_length=200,
        widget=forms.TextInput(attrs={'placeholder': 'Task name or description'}),
    )
    category = forms.ChoiceField(
        required=False,
        choices=[('', 'All categories')] + Task.Category.choices,
    )
    priority = forms.ChoiceField(
        required=False,
        choices=[('', 'All priorities')] + Task.Priority.choices,
    )
    status = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All active statuses'),
            ('pending', 'Pending'),
            ('started', 'Started'),
        ],
    )
