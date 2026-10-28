from django.urls import path
from django.contrib.auth import views as auth_views

from . import forms, views

urlpatterns = [
    path("", views.index, name="index"),
    path("accounts/register/", views.register, name="register"),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="myapp/login.html",
            authentication_form=forms.LoginForm,
        ),
        name="login",
    ),
    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path("accounts/profile/", views.profile, name="profile"),
    path("faq/", views.faq_page, name="faq"),
    path("errors/", views.errors_page, name="errors"),
    path("about/", views.about_page, name="about"),
    path("health/", views.health_check, name="health"),
    path("api/generate/", views.generate_excuse, name="generate_excuse"),
    path("api/assistant/", views.assistant_chat, name="assistant_chat"),
    path("api/assistant/feedback/", views.assistant_feedback, name="assistant_feedback"),
    path("api/inspiration/", views.excuse_inspiration, name="excuse_inspiration"),
]
