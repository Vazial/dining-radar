from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from .forms import OrganizerPasswordChangeForm, ThrottledAuthenticationForm

app_name = "authentication"

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(
            authentication_form=ThrottledAuthenticationForm,
            template_name="authentication/login.html",
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "password/change/",
        auth_views.PasswordChangeView.as_view(
            form_class=OrganizerPasswordChangeForm,
            success_url=reverse_lazy("web:home"),
            template_name="authentication/password_change_form.html",
        ),
        name="password_change",
    ),
    path(
        "password/change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="authentication/password_change_done.html"
        ),
        name="password_change_done",
    ),
]
