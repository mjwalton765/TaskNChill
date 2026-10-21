from django.contrib import messages
from django.core import signing
from django.db import transaction
from django.core.paginator import Paginator
from django.utils import timezone
from urllib.parse import urlencode
from django.http import HttpResponseBadRequest
from django.db.models import Case, IntegerField, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .forms import TaskFilterForm, TaskForm
from .models import Task, TaskHistory


SORT_ORDERS = {
    'category': ['home', 'school', 'work', ''],
    'priority': ['high', 'medium', 'low'],
    'status': ['pending', 'started', 'completed'],
}


def list_context(request, tasks):
    sort = request.GET.get('sort', '')
    if sort not in SORT_ORDERS:
        sort = ''
    descending = request.GET.get('direction') == 'desc'
    if sort:

        rules = []
        for index, value in enumerate(SORT_ORDERS[sort]):
            condition = {sort: value}
            rules.append(When(**condition, then=Value(index)))
        rank = Case(
            *rules,
            default=Value(len(SORT_ORDERS[sort])),
            output_field=IntegerField(),
        )
        if descending:
            tasks = tasks.order_by(rank.desc(), '-created_at', '-pk')
        else:
            tasks = tasks.order_by(rank.asc(), '-created_at', '-pk')
    else:
        tasks = tasks.order_by('-created_at', '-pk')
    links = []
    for key, label in [('category', 'Category'), ('priority', 'Priority'), ('status', 'Status')]:
        params = request.GET.copy()
        params.pop('page', None)
        params['sort'] = key
        params['direction'] = 'asc'
        indicator = '\u2195'
        if sort == key:
            if descending:
                indicator = '\u2193'
            else:
                indicator = '\u2191'
                params['direction'] = 'desc'
        links.append({'label': label, 'key': key,
                      'url': '?' + params.urlencode() + '#task-results',
                      'active': sort == key,
                      'indicator': indicator})
    params = request.GET.copy()
    params.pop('page', None)
    params.pop('sort', None)
    params.pop('direction', None)
    return {'tasks': tasks, 'sort_links': links,
            'newest_url': '?' + params.urlencode() + '#task-results',
            'sort': sort}


@require_GET
def task_list(request):
    context = {
        'tasks': Task.objects.filter(is_deleted=False).exclude(status='completed').order_by('-created_at', '-pk'),
        'heading': 'Active tasks',
        'is_search': False,
    }
    return render_list(request, context)


def add_task(request):
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('task_list')
    else:
        form = TaskForm()
    return render(request, 'tasks/task_add.html', {'form': form})


@require_GET
def find_tasks(request):
    return render(request, 'tasks/task_find.html', {'filters': TaskFilterForm(request.GET or None)})


@require_GET
def search_results(request):
    filters = TaskFilterForm(request.GET)
    tasks = Task.objects.filter(is_deleted=False).exclude(status='completed')
    if filters.is_valid():
        query = filters.cleaned_data['q']
        if query:
            tasks = tasks.filter(Q(title__icontains=query) | Q(description__icontains=query))
        category = filters.cleaned_data['category']
        priority = filters.cleaned_data['priority']
        status = filters.cleaned_data['status']
        if category:
            tasks = tasks.filter(category=category)
        if priority:
            tasks = tasks.filter(priority=priority)
        if status:
            tasks = tasks.filter(status=status)
    else:
        return render(request, 'tasks/task_find.html', {'filters': filters})
    context = list_context(request, tasks)
    params = request.GET.copy()
    params.pop('page', None)
    params.pop('sort', None)
    params.pop('direction', None)
    context.update(heading='Search results', is_search=True,
                   refine_url=reverse('find_tasks') + '?' + params.urlencode())
    return render_list(request, context)


def safe_list_url(value, fallback):
    paths = [reverse('task_list'), reverse('search_results'),
             reverse('completed_tasks'), reverse('deleted_tasks')]
    if isinstance(value, str) and value.split('?', 1)[0] in paths:
        return value
    return reverse(fallback)


@transaction.atomic
def edit_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id, is_deleted=False)
    fallback = 'task_list'
    if task.completed:
        fallback = 'completed_tasks'
    return_to = reverse(fallback)
    if request.method == 'POST':
        token = request.POST.get('return_token', '')
        form = TaskForm(request.POST, instance=task)
    else:
        token = request.GET.get('return_token', '')
        form = TaskForm(instance=task)
    if token:
        try:
            origin = signing.loads(token, salt='task-edit-return', max_age=86400)
            if origin['task_id'] != task_id:
                raise ValueError
            return_to = safe_list_url(origin['url'], fallback)
        except (signing.BadSignature, KeyError, TypeError, ValueError):
            return HttpResponseBadRequest('Open the editor from a fresh task list and try again.')
    updated_at = None
    if task.updated_at:
        updated_at = task.updated_at.isoformat()
    version = {'task_id': task.pk, 'updated_at': updated_at}
    edit_version = signing.dumps(version, salt='task-edit-version')
    status = 200
    if request.method == 'POST':
        form.is_valid()
        submitted_version = request.POST.get('edit_version', '')
        try:
            if signing.loads(submitted_version, salt='task-edit-version', max_age=86400) != version:
                raise ValueError
        except (signing.BadSignature, ValueError, TypeError):
            form.add_error(None, 'This task changed or the editor expired. Reopen it from the list before saving. Your changes have not been saved.')
            status = 409
            edit_version = submitted_version
        if status == 200 and form.is_valid():
            form.save()
            return redirect(return_to)
    return render(request, 'tasks/task_edit.html', {
        'task': task, 'form': form, 'return_to': return_to, 'return_token': token,
        'edit_version': edit_version,
    }, status=status)


def render_list(request, context):
    page = Paginator(context['tasks'], 10).get_page(request.GET.get('page'))
    tasks = list(page.object_list)
    context.update(tasks=tasks, page=page, total_tasks=page.paginator.count)
    scope = context.get('scope', 'active')
    context['scope'] = scope
    params = request.GET.copy()
    if page.number > 1:
        params['page'] = page.number
    else:
        params.pop('page', None)
    list_url = request.path
    if params:
        list_url += '?' + params.urlencode()
    context['list_url'] = list_url
    for key, number in [('previous_url', page.number - 1), ('next_url', page.number + 1)]:
        links = params.copy()
        links['page'] = number
        context[key] = request.path + '?' + links.urlencode() + '#task-results'
    context['selection_token'] = signing.dumps(
        {'ids': [task.pk for task in tasks], 'scope': scope,
         'return_to': list_url}, salt='task-selection')
    return render(request, 'tasks/task_list.html', context)


@require_GET
def completed_tasks(request):
    return render_list(request, {
        'tasks': Task.objects.filter(is_deleted=False, status='completed').order_by('-created_at', '-pk'),
        'heading': 'Completed tasks', 'scope': 'completed',
    })


@require_GET
def deleted_tasks(request):
    return render_list(request, {
        'tasks': Task.objects.filter(is_deleted=True).order_by('-created_at', '-pk'),
        'heading': 'Deleted tasks', 'scope': 'deleted',
    })


def selected_ids(request, selection):
    ids = set()
    for value in request.POST.getlist('selected'):
        task_id = int(value)
        if task_id not in selection['ids']:
            raise ValueError
        ids.add(task_id)
    if not ids:
        raise ValueError
    return ids


def action_message(request, count, label):
    noun = 'tasks'
    if count == 1:
        noun = 'task'
    messages.success(request, f'{count} {noun} {label}')


@require_POST
@transaction.atomic
def task_action(request):


    try:
        selection = signing.loads(request.POST.get('selection_token', ''), salt='task-selection', max_age=86400)
        ids = selected_ids(request, selection)
        scope = selection['scope']
        if scope not in ('active', 'completed', 'deleted'):
            raise ValueError
    except (signing.BadSignature, ValueError, KeyError, TypeError):
        return HttpResponseBadRequest('Select tasks from a fresh list and try again.')

    tasks = Task.objects.filter(pk__in=ids, is_deleted=(scope == 'deleted'))
    if scope == 'completed':
        tasks = tasks.filter(status='completed')
    elif scope == 'active':
        tasks = tasks.exclude(status='completed')
    action = request.POST.get('action')
    allowed = {
        'active': {'edit', 'start', 'complete', 'delete', 'repeat'},
        'completed': {'edit', 'delete', 'restore', 'repeat'},
        'deleted': {'restore', 'purge', 'repeat'},
    }
    selected_tasks = list(tasks.order_by('created_at', 'pk'))
    if action not in allowed[scope] or len(selected_tasks) != len(ids):
        return HttpResponseBadRequest('The selection changed. Refresh the list and try again.')
    destination = {'active': 'task_list', 'completed': 'completed_tasks', 'deleted': 'deleted_tasks'}[scope]
    return_to = safe_list_url(selection.get('return_to'), destination)
    if action == 'edit':
        if len(ids) != 1:
            return HttpResponseBadRequest('Select exactly one task to edit.')
        task_id = selected_tasks[0].pk
        token = signing.dumps({'task_id': task_id, 'url': return_to}, salt='task-edit-return')
        return redirect(reverse('edit_task', args=[task_id]) + '?' + urlencode({'return_token': token}))
    if action == 'purge':
        if request.POST.get('confirmed') != 'yes':
            return render(request, 'tasks/confirm_delete.html', {
                'tasks': tasks.order_by('pk'), 'return_to': return_to,
                'confirmation_token': signing.dumps(sorted(ids), salt='permanent-delete'),
            })
        try:
            confirmed_ids = signing.loads(request.POST.get('confirmation_token', ''), salt='permanent-delete', max_age=600)
            if set(confirmed_ids) != ids:
                raise ValueError
        except (signing.BadSignature, ValueError, TypeError):
            return HttpResponseBadRequest('Deletion confirmation expired. Start again from Deleted.')
        for task in selected_tasks:
            task.record_history('purged')
        count = len(selected_tasks)
        tasks.delete()
        action_message(request, count, 'Permanently deleted')
    elif action == 'repeat':
        for task in selected_tasks:
            task.repeat()
        count = len(selected_tasks)
        action_message(request, count, 'Repeated')
    else:
        now = timezone.now()
        for task in selected_tasks:
            if action == 'delete':
                task.is_deleted = True
            elif action == 'restore':
                task.is_deleted = False
                task.status = Task.Status.STARTED
                task.completed_at = None
                task.restored_at = now
            elif action == 'start':
                task.status = Task.Status.STARTED
            elif action == 'complete':
                task.status = Task.Status.COMPLETED

            if action == 'restore':

                task.save(preserve_status_dates=True, history_action='restored')
            else:
                task.save()
        count = len(selected_tasks)
        labels = {'delete': 'Deleted', 'restore': 'Restored', 'complete': 'Completed'}
        if action in labels:
            action_message(request, count, labels[action])
    return redirect(return_to)


@require_GET
def task_history(request):
    entries = TaskHistory.objects.all()
    page = Paginator(entries, 10).get_page(request.GET.get('page'))
    displayed = list(page.object_list)
    list_url = reverse('task_history')
    if page.number > 1:
        list_url += f'?page={page.number}'
    return render(request, 'tasks/history.html', {
        'entries': displayed, 'page': page, 'total_entries': page.paginator.count,
        'list_url': list_url,
        'previous_url': reverse('task_history') + f'?page={page.number - 1}#task-results',
        'next_url': reverse('task_history') + f'?page={page.number + 1}#task-results',
        'selection_token': signing.dumps({'ids': [entry.pk for entry in displayed],
                                         'page': page.number}, salt='history-selection'),
    })


@require_POST
def delete_history(request):
    try:
        if request.POST.get('confirmed') == 'yes':
            choice = signing.loads(request.POST.get('confirmation_token', ''),
                                   salt='history-delete', max_age=600)
            mode = choice['mode']
            if mode == 'selected':
                entries = TaskHistory.objects.filter(pk__in=choice['ids'])
            elif mode == 'all':
                entries = TaskHistory.objects.filter(pk__lte=choice['through_id'])
            else:
                raise ValueError
            count, _ = entries.delete()
            messages.success(request, f'{count} history {"entry" if count == 1 else "entries"} Deleted')
            return redirect(reverse('task_history') + f'?page={choice["page"]}')

        selection = signing.loads(request.POST.get('selection_token', ''),
                                  salt='history-selection', max_age=86400)
        mode = request.POST.get('action')
        choice = {'mode': mode, 'page': selection['page']}
        if mode == 'selected':
            ids = selected_ids(request, selection)
            entries = TaskHistory.objects.filter(pk__in=ids)
            if entries.count() != len(ids):
                raise ValueError
            choice['ids'] = sorted(ids)
        elif mode == 'all':
            newest_id = TaskHistory.objects.order_by('-pk').values_list('pk', flat=True).first()
            if newest_id is None:
                raise ValueError
            choice['through_id'] = newest_id
            entries = TaskHistory.objects.filter(pk__lte=newest_id)
        else:
            raise ValueError
        count = entries.count()
        return render(request, 'tasks/confirm_history_delete.html', {
            'count': count, 'clear_all': mode == 'all',
            'entries': entries if mode == 'selected' else [],
            'confirmation_token': signing.dumps(choice, salt='history-delete'),
            'return_to': reverse('task_history') + f'?page={selection["page"]}',
        })
    except (signing.BadSignature, ValueError, TypeError, KeyError):
        return HttpResponseBadRequest('The history selection or confirmation expired. Return to History and try again.')
