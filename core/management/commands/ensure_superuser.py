"""
Creates a superuser from DJANGO_SUPERUSER_USERNAME / _EMAIL / _PASSWORD
environment variables if no superuser already exists. Safe to run on
every container start (Render free tier has no shell/SSH access, so
`createsuperuser`'s interactive prompt isn't usable there -- this is
what makes first-deploy fully hands-off instead of requiring a manual
one-time step you can't actually perform on a free instance).
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a superuser from env vars if none exists yet (idempotent, non-interactive)."

    def handle(self, *args, **options):
        User = get_user_model()

        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write("A superuser already exists -- skipping.")
            return

        username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

        if not username or not password:
            self.stdout.write(self.style.WARNING(
                "No DJANGO_SUPERUSER_USERNAME/PASSWORD set and no superuser exists yet -- "
                "set those environment variables and redeploy, or run "
                "'python manage.py createsuperuser' somewhere with shell access."
            ))
            return

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Created superuser '{username}'."))
