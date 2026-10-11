#!/usr/bin/env bash
# Build the web image, push it to ECR, register a new task definition revision
# and roll the ECS service onto it (KEN-37). Run by a human from
# projects/dining-radar with AWS credentials (this repository's AI runtimes
# hold none): `AWS_PROFILE=<profile> deploy/deploy.sh`.
#
# The image tag is the git commit, so the working tree must be clean -- the tag
# would otherwise name code that is not what was built. ECR tags are immutable;
# if the commit's image is already in ECR the build and push are skipped and
# only the task definition and service are (re)applied.
#
# Requires: aws CLI v2, jq, and podman or docker.
set -o errexit
set -o nounset
set -o pipefail

region="${AWS_REGION:-ap-northeast-1}"
cluster="${ECS_CLUSTER:-dining-radar}"
service="${ECS_SERVICE:-dining-radar-web}"
repository="${ECR_REPOSITORY:-dining-radar-web}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"
cd "${project_dir}"

if [[ -n "$(git status --porcelain -- .)" ]]; then
    echo "Working tree has uncommitted changes under ${project_dir}; commit first." >&2
    exit 1
fi

if command -v podman >/dev/null 2>&1; then
    engine=(podman)
    build_flags=(--platform linux/amd64 --format docker)
elif command -v docker >/dev/null 2>&1; then
    engine=(docker)
    build_flags=(--platform linux/amd64)
else
    echo "Neither podman nor docker is installed." >&2
    exit 1
fi

account_id="$(aws sts get-caller-identity --query Account --output text)"
registry="${account_id}.dkr.ecr.${region}.amazonaws.com"
tag="$(git rev-parse --short HEAD)"
image="${registry}/${repository}:${tag}"

if aws ecr describe-images --region "${region}" --repository-name "${repository}" \
    --image-ids "imageTag=${tag}" >/dev/null 2>&1; then
    echo "Image ${repository}:${tag} is already in ECR; skipping build and push."
else
    echo "Building ${image}"
    aws ecr get-login-password --region "${region}" \
        | "${engine[@]}" login --username AWS --password-stdin "${registry}"
    "${engine[@]}" build "${build_flags[@]}" -t "${image}" .
    "${engine[@]}" push "${image}"
fi

task_definition="$(mktemp)"
trap 'rm -f "${task_definition}"' EXIT
sed -e "s/<AWS_ACCOUNT_ID>/${account_id}/g" \
    -e "s/<AWS_REGION>/${region}/g" \
    -e "s/<TAG>/${tag}/g" \
    deploy/ecs/task-definition.json > "${task_definition}"
if grep -n '<[A-Z_]*>' "${task_definition}"; then
    echo "Unresolved placeholders remain in the task definition." >&2
    exit 1
fi

revision_arn="$(aws ecs register-task-definition --region "${region}" \
    --cli-input-json "file://${task_definition}" \
    --query taskDefinition.taskDefinitionArn --output text)"
echo "Registered ${revision_arn}"

aws ecs update-service --region "${region}" --cluster "${cluster}" --service "${service}" \
    --task-definition "${revision_arn}" --query service.serviceName --output text >/dev/null

echo "Waiting for ${service} to become stable (the circuit breaker rolls back on failure)..."
aws ecs wait services-stable --region "${region}" --cluster "${cluster}" --services "${service}"

aws ecs describe-services --region "${region}" --cluster "${cluster}" --services "${service}" \
    --query 'services[0].deployments[].[status,taskDefinition,runningCount,rolloutState]' \
    --output text

# A rolled-back deployment also becomes "stable", on the previous revision.
# Succeed only if the service is actually running the revision just registered.
running_revision="$(aws ecs describe-services --region "${region}" --cluster "${cluster}" \
    --services "${service}" --query 'services[0].taskDefinition' --output text)"
if [[ "${running_revision}" != "${revision_arn}" ]]; then
    echo "Deployment did not take: service runs ${running_revision}, expected ${revision_arn}." >&2
    exit 1
fi
echo "Deployed ${repository}:${tag}"
