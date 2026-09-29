# ECS Fargate web image (ADR-0067). Built and pushed to ECR by a human
# (this repository's AI runtimes hold no AWS credentials, KEN-31 scope). The
# companion Caddy sidecar image lives in deploy/caddy/Dockerfile -- this
# image only ever serves plain HTTP on localhost inside the task network
# namespace; TLS termination happens in the sidecar, never here.
FROM python:3.12-slim

# Matches render.yaml's PYTHON_VERSION pin (3.12.13) at the minor-version
# level; python:3.12-slim tracks the latest 3.12.x patch instead of pinning
# an exact patch tag, since unlike Render's buildpack this image has no
# separate mechanism to bump a patch pin over time.

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System package needed only by the container healthcheck below (this slim
# base has no curl). Layer is cached separately from the Python deps layer.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
RUN python -m pip install --no-cache-dir -e .

# collectstatic needs a non-empty DJANGO_SECRET_KEY to import settings.py
# (settings.py raises RuntimeError otherwise) but never touches the
# database or a real ALLOWED_HOSTS value, so a build-time-only placeholder
# is enough. This value is not an ENV instruction -- it does not persist
# into the running container's environment, and even if it did, the ECS
# task definition's own "secrets" entry for DJANGO_SECRET_KEY (SSM
# Parameter Store) always overrides it at runtime. It must never be relied
# on for anything but this one offline build step.
RUN DJANGO_SECRET_KEY=build-time-placeholder-not-used-at-runtime \
    python manage.py collectstatic --no-input

COPY manage.py ./
COPY deploy/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000

# Read directly by the app container's own ECS health check (bypasses the
# Caddy sidecar entirely -- there is no ALB target group in this topology,
# ADR-0067). Plain HTTP against localhost inside the task's network
# namespace, same as Render's probe reaching this service without going
# through a TLS-terminating edge; the existing SECURE_REDIRECT_EXEMPT for
# "^healthz$" in settings.py already covers this path, no code change
# needed for Fargate.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

ENTRYPOINT ["docker-entrypoint.sh"]
