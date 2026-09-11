#!/usr/bin/env bash
# Vercel build step: compile Tailwind, collect static files, run migrations.
set -euo pipefail

echo "--- Installing Node deps & building Tailwind ---"
npm ci
npm run tailwind:build

echo "--- Collecting static files ---"
python manage.py collectstatic --noinput

echo "--- Running migrations ---"
python manage.py migrate --noinput

echo "Build complete."
