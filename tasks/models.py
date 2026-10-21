from django.db import models, transaction
from django.utils import timezone



class RepeatGroup(models.Model):
    base_title = models.CharField(max_length=200, unique=True)
    last_number = models.PositiveIntegerField(default=0)


class Task(models.Model):
    class Category(models.TextChoices):
        WORK = 'work', 'Work'
        SCHOOL = 'school', 'School'
        HOME = 'home', 'Home'

    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        STARTED = 'started', 'Started'
        COMPLETED = 'completed', 'Completed'

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=10, choices=Category.choices, blank=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    repeat_group = models.ForeignKey(RepeatGroup, null=True, blank=True, on_delete=models.PROTECT)
    repeat_number = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['repeat_group', 'repeat_number'], name='unique_task_repeat_number'),
        ]

    pending_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    restored_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    @transaction.atomic
    def save(self, *args, **kwargs):
        history_action = kwargs.pop('history_action', None)
        history_details = kwargs.pop('history_details', '')
        preserve_status_dates = kwargs.pop('preserve_status_dates', False)
        now = timezone.now()
        previous = None
        if self.pk:
            previous = Task.objects.filter(pk=self.pk).first()
        changed = {'updated_at'}
        self.updated_at = now
        if not preserve_status_dates and (previous is None or previous.status != self.status):
            if self.status == self.Status.PENDING:
                self.pending_at = now
                changed.add('pending_at')
            elif self.status == self.Status.STARTED:
                self.started_at = now
                changed.add('started_at')
            elif self.status == self.Status.COMPLETED:
                self.completed_at = now
                changed.add('completed_at')

        if previous and previous.status == self.Status.COMPLETED and self.status != self.Status.COMPLETED:
            self.completed_at = None
            changed.add('completed_at')
        if self.is_deleted and (previous is None or not previous.is_deleted):
            self.deleted_at = now
            changed.add('deleted_at')
        if kwargs.get('update_fields') is not None:
            update_fields = set(kwargs['update_fields'])
            update_fields.update(changed)
            kwargs['update_fields'] = update_fields
        super().save(*args, **kwargs)
        details = self.describe_changes(previous)
        if history_action is None:
            if previous is None:
                history_action = 'created'
            elif self.is_deleted and not previous.is_deleted:
                history_action = 'deleted'
            elif previous.is_deleted and not self.is_deleted:
                history_action = 'restored'
            elif self.status != previous.status:
                history_action = self.status
            elif details:
                history_action = 'edited'
        if history_action:
            if not history_details:
                history_details = '\n'.join(details)
            self.record_history(history_action, history_details)

    def describe_changes(self, previous):
        if previous is None:
            return []
        fields = [
            ('Name', previous.title, self.title),
            ('Description', previous.description, self.description),
            ('Category', previous.get_category_display(), self.get_category_display()),
            ('Priority', previous.get_priority_display(), self.get_priority_display()),
            ('Status', previous.get_status_display(), self.get_status_display()),
        ]
        details = []
        for label, before, after in fields:
            if before != after:
                if not before:
                    before = '(empty)'
                if not after:
                    after = '(empty)'
                details.append(f'{label}: {before} -> {after}')
        return details

    @transaction.atomic
    def repeat(self):
        original = Task.objects.select_for_update().get(pk=self.pk)
        if original.repeat_group_id is None:
            group, _ = RepeatGroup.objects.get_or_create(base_title=original.title)
            Task.objects.filter(pk=original.pk).update(repeat_group=group)
        else:
            group = original.repeat_group
        group = RepeatGroup.objects.select_for_update().get(pk=group.pk)
        number = group.last_number
        while True:
            number += 1
            suffix = f'-{number}'
            title = group.base_title[:200 - len(suffix)] + suffix
            if not Task.objects.filter(title__iexact=title).exists():
                break
        group.last_number = number
        group.save(update_fields=['last_number'])
        copy = Task(
            title=title, description=original.description,
            category=original.category, priority=original.priority,
            repeat_group=group, repeat_number=number,
        )
        copy.save(history_action='repeated', history_details=f'Repeated from {original.title}. New task is Pending.')
        return copy

    def record_history(self, action, details=''):
        return TaskHistory.objects.create(
            task=self, task_number=self.pk, task_title=self.title,
            action=action, details=details,
        )

    @property
    def status_date(self):
        if self.is_deleted:
            return self.deleted_at
        if self.status == self.Status.PENDING:
            return self.pending_at
        if self.status == self.Status.STARTED:
            return self.started_at
        if self.status == self.Status.COMPLETED:
            return self.completed_at

    @property
    def completed(self):
        return self.status == self.Status.COMPLETED

    def __str__(self):
        return self.title


class TaskHistory(models.Model):
    class Action(models.TextChoices):
        CREATED = 'created', 'Created'
        PENDING = 'pending', 'Pending'
        STARTED = 'started', 'Started'
        COMPLETED = 'completed', 'Completed'
        RESTORED = 'restored', 'Restored'
        REPEATED = 'repeated', 'Repeated'
        EDITED = 'edited', 'Edited'
        DELETED = 'deleted', 'Deleted'
        PURGED = 'purged', 'Permanently deleted'

    task = models.ForeignKey(Task, null=True, blank=True, on_delete=models.SET_NULL)
    task_number = models.PositiveBigIntegerField()
    task_title = models.CharField(max_length=200)
    action = models.CharField(max_length=20, choices=Action.choices)
    details = models.TextField(blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-occurred_at', '-pk']
