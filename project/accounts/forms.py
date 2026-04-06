from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from .models import User


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "password1", "password2")
        widgets = {
            "username": forms.TextInput(attrs={"class": "input", "autocomplete": "username"}),
            "email": forms.EmailInput(attrs={"class": "input", "autocomplete": "email"}),
            "first_name": forms.TextInput(attrs={"class": "input"}),
            "last_name": forms.TextInput(attrs={"class": "input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update({"class": "input", "autocomplete": "new-password"})
        self.fields["password2"].widget.attrs.update({"class": "input", "autocomplete": "new-password"})

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.is_staff = False
        user.is_superuser = False
        if commit:
            user.save()
        return user


class StaffCreateForm(forms.Form):
    """Used only by superusers to create staff accounts (not self-service)."""

    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"class": "input"}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={"class": "input"}))
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"class": "input", "autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(attrs={"class": "input", "autocomplete": "new-password"}),
    )

    def clean_username(self):
        u = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=u).exists():
            raise ValidationError("That username is already taken.")
        return u

    def clean(self):
        data = super().clean()
        p1 = data.get("password1")
        p2 = data.get("password2")
        if p1 and p2 and p1 != p2:
            raise ValidationError("Passwords do not match.")
        return data

    def save(self):
        return User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data.get("email") or "",
            password=self.cleaned_data["password1"],
            is_staff=True,
            is_superuser=False,
        )


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone", "profile_picture")
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "input"}),
            "last_name": forms.TextInput(attrs={"class": "input"}),
            "email": forms.EmailInput(attrs={"class": "input"}),
            "phone": forms.TextInput(attrs={"class": "input"}),
        }
