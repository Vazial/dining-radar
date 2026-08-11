"""Provision the first invite-only organizer from write-only runtime secrets."""

import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Create the initial organizer if runtime bootstrap secrets are configured."

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-configured",
            action="store_true",
            help="Exit successfully when both bootstrap variables are absent.",
        )

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_BOOTSTRAP_ORGANIZER_USERNAME", "").strip()
        password = os.environ.get("DJANGO_BOOTSTRAP_ORGANIZER_PASSWORD", "")

        if not username and not password and options["if_configured"]:
            self.stdout.write("Organizer bootstrap is not configured; nothing to do.")
            return
        if not username or not password:
            raise CommandError(
                "Both DJANGO_BOOTSTRAP_ORGANIZER_USERNAME and "
                "DJANGO_BOOTSTRAP_ORGANIZER_PASSWORD are required."
            )

        user_model = get_user_model()
        username_field = user_model._meta.get_field(user_model.USERNAME_FIELD)
        if username_field.max_length and len(username) > username_field.max_length:
            raise CommandError("The configured organizer username is too long.")

        with transaction.atomic():
            if user_model.objects.filter(**{user_model.USERNAME_FIELD: username}).exists():
                self.stdout.write("The configured organizer already exists; nothing changed.")
                return
            user = user_model(**{user_model.USERNAME_FIELD: username})
            try:
                validate_password(password, user=user)
            except ValidationError as error:
                raise CommandError(
                    "The configured organizer password is not acceptable."
                ) from error
            user.is_active = True
            user.is_staff = False
            user.is_superuser = False
            user.set_password(password)
            user.full_clean(exclude={"password"})
            user.save()

        self.stdout.write(self.style.SUCCESS("The initial organizer was created."))
