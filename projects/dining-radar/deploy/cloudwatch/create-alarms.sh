#!/usr/bin/env bash
# Creates the basic CloudWatch alarms in alarms.json (ADR-0067, KEN-31).
# Run by a human after the ECS service and reattach Lambda exist (this
# repository's AI runtimes hold no AWS credentials). Requires the AWS CLI
# and jq. No AlarmActions/SNS topic is set here -- ADR-0067 did not decide
# a notification channel, so these alarms are visible in the CloudWatch
# console/API only until a human adds one.
set -o errexit
set -o nounset
set -o pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

jq -c '.[]' "${script_dir}/alarms.json" | while read -r alarm; do
    name=$(jq -r '.AlarmName' <<<"${alarm}")
    echo "Creating alarm: ${name}"
    aws cloudwatch put-metric-alarm \
        --alarm-name "$(jq -r '.AlarmName' <<<"${alarm}")" \
        --alarm-description "$(jq -r '.AlarmDescription' <<<"${alarm}")" \
        --namespace "$(jq -r '.Namespace' <<<"${alarm}")" \
        --metric-name "$(jq -r '.MetricName' <<<"${alarm}")" \
        --dimensions "$(jq -c '.Dimensions' <<<"${alarm}")" \
        --statistic "$(jq -r '.Statistic' <<<"${alarm}")" \
        --period "$(jq -r '.Period' <<<"${alarm}")" \
        --evaluation-periods "$(jq -r '.EvaluationPeriods' <<<"${alarm}")" \
        --threshold "$(jq -r '.Threshold' <<<"${alarm}")" \
        --comparison-operator "$(jq -r '.ComparisonOperator' <<<"${alarm}")" \
        --treat-missing-data "$(jq -r '.TreatMissingData' <<<"${alarm}")"
done
