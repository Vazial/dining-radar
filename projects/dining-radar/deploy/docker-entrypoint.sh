#!/usr/bin/env bash
# Container entrypoint for the ECS Fargate app container (ADR-0067, KEN-31).
#
# build.sh (Render) runs the same three post-install steps below once per
# build, ahead of the deploy that follows a green CI check. This image has
# no equivalent separate "build then deploy" step -- the same image is
# reused across restarts -- so those three steps move here, run once on
# every container start instead. collectstatic stays a Dockerfile RUN step
# (build-time only, matches Render's build.sh position, and never needs the
# database).
set -o errexit
set -o nounset
set -o pipefail

python manage.py migrate --no-input
python manage.py provision_organizer --if-configured
python manage.py check --deploy

exec gunicorn dining_radar.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --threads 4 \
    --timeout 60
