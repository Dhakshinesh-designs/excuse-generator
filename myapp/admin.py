from django.contrib import admin

from .models import ErrorCode, FAQ, SupportTicket


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "order")
    search_fields = ("question", "answer", "keywords")
    ordering = ("order", "id")


@admin.register(ErrorCode)
class ErrorCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "order")
    search_fields = ("code", "title", "explanation")
    ordering = ("order", "code")


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("reference", "question", "user__username")
    readonly_fields = ("reference", "created_at")
