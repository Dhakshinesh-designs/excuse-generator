import uuid

from django.conf import settings
from django.db import models


class FAQ(models.Model):
    question = models.CharField(max_length=240)
    answer = models.TextField()
    keywords = models.CharField(max_length=400, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "frequently asked question"
        verbose_name_plural = "frequently asked questions"

    def __str__(self):
        return self.question


class ErrorCode(models.Model):
    code = models.CharField(max_length=16, unique=True)
    title = models.CharField(max_length=120)
    explanation = models.TextField()
    suggested_action = models.TextField()
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "code"]

    def __str__(self):
        return f"{self.code}: {self.title}"


class SupportTicket(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        RESOLVED = "resolved", "Resolved"

    reference = models.CharField(max_length=12, unique=True, editable=False)
    question = models.TextField(max_length=2000)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="support_tickets",
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.OPEN
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = uuid.uuid4().hex[:10].upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference} ({self.get_status_display()})"
