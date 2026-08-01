from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.core.exceptions import ValidationError

from .throttle import LoginThrottle


class ThrottledAuthenticationForm(AuthenticationForm):
    """Django's password validation with a generic, runtime-only failure limiter."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.throttled = False
        self.fields["username"].widget.attrs["data-testid"] = "auth-login-identifier"
        self.fields["password"].widget.attrs["data-testid"] = "auth-password"

    def clean(self):
        username = self.cleaned_data.get("username", "")
        throttle = LoginThrottle(self.request, username)

        if throttle.is_limited():
            self.throttled = True
            raise ValidationError(self.error_messages["invalid_login"], code="invalid_login")

        try:
            cleaned_data = super().clean()
        except ValidationError:
            throttle.record_failure()
            raise

        throttle.clear()
        return cleaned_data


class OrganizerPasswordChangeForm(PasswordChangeForm):
    """Adds stable acceptance control identifiers without changing validation."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].widget.attrs["data-testid"] = "auth-current-password"
        self.fields["new_password1"].widget.attrs["data-testid"] = "auth-new-password"
        self.fields["new_password2"].widget.attrs["data-testid"] = "auth-new-password-confirmation"
