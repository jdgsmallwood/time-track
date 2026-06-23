#!/bin/sh
set -e

echo "Waiting for DB to be ready..."
python manage.py migrate --noinput

echo "Bootstrapping superuser..."
python manage.py bootstrap_superuser

echo "Starting application..."
exec "$@"
