#!/usr/bin/env bash
set -o errexit
set -o nounset
set -o pipefail

python -m pip install --disable-pip-version-check -e .
python manage.py collectstatic --no-input
python manage.py migrate --no-input
python manage.py provision_organizer --if-configured
python manage.py check --deploy
