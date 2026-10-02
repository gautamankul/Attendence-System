from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from tracker import views as tracker_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # Auth — the login page is the first thing a visitor sees.
    path("", auth_views.LoginView.as_view(template_name="tracker/login.html"), name="login"),
    path("login/", auth_views.LoginView.as_view(template_name="tracker/login.html"), name="login_alt"),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
    path("register/", tracker_views.register, name="register"),

    # Tracker — only reachable once signed in (see @login_required).
    path("tracker/", tracker_views.tracker_view, name="tracker"),
    path("tracker/set-status/", tracker_views.set_status, name="set_status"),
    path("tracker/download/", tracker_views.download_report, name="download_report"),
]
