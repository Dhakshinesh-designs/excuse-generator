from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

CONTROL_CLASS = (
    "focus-ring mt-1 block w-full rounded-xl border border-white/15 "
    "bg-zinc-900 px-4 py-3 text-white"
)


class RegistrationForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = CONTROL_CLASS

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username",)


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = CONTROL_CLASS


class ProfileForm(forms.Form):
    display_name = forms.CharField(max_length=80)
    email = forms.EmailField(required=False)
    bio = forms.CharField(max_length=500, required=False, widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = CONTROL_CLASS
