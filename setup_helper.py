"""
Helper functions for setup_local.bat. Not part of the running app --
purely a setup-time convenience so the batch file can stay simple.
"""
import os
import secrets
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / '.env'
ENV_EXAMPLE_PATH = BASE_DIR / '.env.example'

PLACEHOLDER_SECRET = 'change-this-to-a-long-random-string'


def generate_env():
    """Creates .env from .env.example on first run, and replaces any
    still-default secret values with real random ones -- safe to re-run,
    it never touches values you've already customized."""
    if not ENV_PATH.exists():
        if not ENV_EXAMPLE_PATH.exists():
            print("ERROR: .env.example not found.")
            sys.exit(1)
        ENV_PATH.write_text(ENV_EXAMPLE_PATH.read_text())
        print("Created .env from .env.example.")

    content = ENV_PATH.read_text()
    replacements = 0

    for key in ('SECRET_KEY', 'DEVICE_ENROLLMENT_KEY'):
        line_prefix = f'{key}={PLACEHOLDER_SECRET}'
        if line_prefix in content:
            new_value = secrets.token_urlsafe(32)
            content = content.replace(line_prefix, f'{key}={new_value}')
            replacements += 1

    if replacements:
        ENV_PATH.write_text(content)
        print(f"Generated {replacements} secret value(s) in .env automatically.")
    else:
        print(".env already has custom secrets configured -- left as-is.")


def _get_env_value(key):
    if not ENV_PATH.exists():
        return ''
    for line in ENV_PATH.read_text().splitlines():
        if line.startswith(f'{key}='):
            return line.split('=', 1)[1].strip()
    return ''


def ensure_superuser():
    """Interactive first-admin-account creation, skipped automatically if
    one already exists (safe to re-run setup_local.bat any time)."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'itam_backend.settings')
    import django
    django.setup()
    from django.contrib.auth import get_user_model

    User = get_user_model()
    if User.objects.filter(is_superuser=True).exists():
        print("An admin account already exists -- skipping.")
        return

    print()
    print("Create your admin login (used to access the dashboard in your browser):")
    username = input("  Username: ").strip() or 'admin'
    email = input("  Email (optional): ").strip()
    import getpass
    password = getpass.getpass("  Password: ")
    while not password:
        password = getpass.getpass("  Password cannot be empty. Password: ")

    User.objects.create_superuser(username=username, email=email, password=password)
    print(f"Admin account '{username}' created.")


def show_summary():
    enrollment_key = _get_env_value('DEVICE_ENROLLMENT_KEY')
    print()
    print("=" * 62)
    print("  READY")
    print("=" * 62)
    print()
    print("Admin dashboard (open this in a browser once the server is running):")
    print("  http://127.0.0.1:8000/admin/")
    print()
    print("In AssetManager's Cloud Sync tab, fill in:")
    print("  Server URL:      http://127.0.0.1:8000")
    print(f"  Enrollment Key:  {enrollment_key}")
    print()
    print("(This is only reachable from THIS PC. See RENDER_DEPLOY.md for a")
    print(" real internet address other branch PCs can reach.)")
    print("=" * 62)


if __name__ == '__main__':
    command = sys.argv[1] if len(sys.argv) > 1 else ''
    {
        'generate_env': generate_env,
        'ensure_superuser': ensure_superuser,
        'show_summary': show_summary,
    }.get(command, lambda: print(f"Unknown command: {command}"))()
