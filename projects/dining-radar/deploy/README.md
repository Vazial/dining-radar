# deploy/ — ECS Fargate publish artifacts (ADR-0067)

Code-side artifacts for the [ADR-0067](../adr/0067-consider-aws-deployment-migration.md)
migration target (KEN-31). The step-by-step human procedure that uses these files —
building/pushing images, creating the SSM parameters, registering the task
definition, wiring the Lambda/EventBridge rule, and cutting over DNS — lives in
[DEPLOYMENT.md](../DEPLOYMENT.md). This file is only an index of what is here and
why; it does not duplicate that procedure (P-04).

| Path | What it is |
|---|---|
| `docker-entrypoint.sh` | App container entrypoint (`../Dockerfile`'s `ENTRYPOINT`). Runs `migrate`/`provision_organizer --if-configured`/`check --deploy` once per container start, then execs gunicorn. |
| `caddy/Dockerfile`, `caddy/Caddyfile` | The TLS-terminating sidecar image. Proxies to the app container over `localhost` inside the shared task network namespace (`awsvpc` mode) — there is no ALB in this topology. |
| `ecs/task-definition.json` | `aws ecs register-task-definition --cli-input-json file://task-definition.json` input. Two containers (`web`, `caddy`), 0.25 vCPU / 0.5GB, secrets sourced from SSM Parameter Store (never committed values). |
| `ecs/service-definition.json` | `aws ecs create-service --cli-input-json file://service-definition.json` input. Single task, public subnet, `assignPublicIp: ENABLED`. `minimumHealthyPercent: 0` is deliberate — this topology accepts a brief connection break on redeploy instead of running two tasks that would fight over the one Elastic IP (ADR-0067's accepted tradeoff). |
| `lambda/reattach_elastic_ip/handler.py` | Re-associates the one Elastic IP onto whichever task is newly `RUNNING`, since every Fargate task restart gets a fresh ENI. |
| `lambda/reattach_elastic_ip/eventbridge-rule.json` | The EventBridge rule matching `ECS Task State Change` events. Registering it as a target (`put-targets`) is not enough on its own — DEPLOYMENT.md §7-4 step 6 also grants the Lambda's *resource-based* policy permission for EventBridge to invoke it (`aws lambda add-permission`). |
| `lambda/reattach_elastic_ip/iam-policy.json` | Least-privilege policy for the Lambda's execution role (plus the AWS-managed `AWSLambdaBasicExecutionRole` for its own logs). |
| `cloudwatch/alarms.json`, `cloudwatch/create-alarms.sh` | Three basic alarms (task CPU, task memory, reattach-Lambda errors). No `AlarmActions`/SNS topic is set — ADR-0067 did not decide a notification channel. |

Every `<PLACEHOLDER>` in these files (account id, region, subnet/security-group ids,
ECR image tags, Elastic IP allocation id) is environment-specific and unknown until
the AWS resources exist, so a human fills them in at the point of use — none of
them are secret values, unlike the SSM-sourced `secrets` entries.
