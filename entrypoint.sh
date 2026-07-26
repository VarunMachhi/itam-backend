#!/bin/sh
set -e

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Ensuring an admin account exists..."
python manage.py ensure_superuser

echo "Starting server..."
exec gunicorn itam_backend.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3
