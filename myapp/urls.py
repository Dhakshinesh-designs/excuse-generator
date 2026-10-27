from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("faq/", views.faq_page, name="faq"),
    path("errors/", views.errors_page, name="errors"),
    path("about/", views.about_page, name="about"),
    path("health/", views.health_check, name="health"),
    path("api/generate/", views.generate_excuse, name="generate_excuse"),
    path("api/assistant/", views.assistant_chat, name="assistant_chat"),
    path("api/assistant/feedback/", views.assistant_feedback, name="assistant_feedback"),
    path("api/inspiration/", views.excuse_inspiration, name="excuse_inspiration"),
]
