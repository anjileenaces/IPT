from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.views import LoginView
from django.core.mail import send_mail
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import RegisterForm

User = get_user_model()


class ClinicLoginView(LoginView):
    template_name = "accounts/login.html"

    def form_valid(self, form):
        messages.success(self.request, "Welcome back — you are logged in.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Login failed. Check your username and password.")
        return super().form_invalid(form)


class RegisterView(CreateView):
    model = User
    form_class = RegisterForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("clinic:dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("clinic:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        messages.success(self.request, "Account created. You are now logged in.")
        email = form.cleaned_data.get("email")
        if email:
            send_mail(
                "Welcome to PawCare",
                "Thanks for registering. You can book visits and manage pet records from your dashboard.",
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=True,
            )
        return response
