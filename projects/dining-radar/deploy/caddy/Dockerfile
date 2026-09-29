# TLS-terminating sidecar for the ECS Fargate task (ADR-0067). Built and
# pushed to its own ECR repository by a human -- see DEPLOYMENT.md. Runs
# alongside the app container in the same task (awsvpc network namespace),
# reached by the public internet directly on the task's Elastic IP; there
# is no ALB in this topology.
FROM caddy:2-alpine

COPY Caddyfile /etc/caddy/Caddyfile
