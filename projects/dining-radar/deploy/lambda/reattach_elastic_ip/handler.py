"""Re-attach the Elastic IP to the newest running task's ENI (ADR-0067).

Deployed and wired to EventBridge by a human (KEN-31: this repository's AI
runtimes hold no AWS credentials). Not covered by this project's pytest
suite -- it has no Django/provider dependency to unit-test against and its
correctness is only observable against a real ECS task's ENI, which is why
DEPLOYMENT.md asks a human to confirm the reattach behavior on real
infrastructure after the first deploy.

Every Fargate task in this single-task, ALB-less topology gets a *new*
elastic network interface (and thus a new private IP) on every restart or
redeploy. Nothing routes the public Elastic IP to that new ENI on its own,
so this function does it: on every "ECS Task State Change" event where the
task has reached RUNNING, it re-associates the one Elastic IP this service
owns onto that task's ENI, replacing whatever the IP was attached to
before (a stopped predecessor task's now-gone ENI, most of the time).
"""

from __future__ import annotations

import os

import boto3

ecs = boto3.client("ecs")
ec2 = boto3.client("ec2")


def handler(event, _context):
    detail = event.get("detail", {})

    if detail.get("lastStatus") != "RUNNING":
        return {"skipped": "not-running", "lastStatus": detail.get("lastStatus")}

    cluster_arn = detail.get("clusterArn")
    task_arn = detail.get("taskArn")
    if not cluster_arn or not task_arn:
        return {"skipped": "missing-cluster-or-task-arn"}

    expected_group = os.environ["ECS_SERVICE_GROUP"]  # e.g. "service:dining-radar-web"
    if detail.get("group") != expected_group:
        return {"skipped": "different-service", "group": detail.get("group")}

    eni_id = _network_interface_id(detail)
    if eni_id is None:
        # awsvpc attachments can briefly report ATTACHING before the ENI id
        # is present even once the task itself is RUNNING; EventBridge will
        # not retry this for us, so ask ECS directly instead of failing.
        eni_id = _network_interface_id_from_ecs(cluster_arn, task_arn)
    if eni_id is None:
        raise RuntimeError(f"no ENI attachment found for task {task_arn}")

    allocation_id = os.environ["ELASTIC_IP_ALLOCATION_ID"]
    response = ec2.associate_address(
        AllocationId=allocation_id,
        NetworkInterfaceId=eni_id,
        AllowReassociation=True,
    )
    return {
        "reassociated": True,
        "taskArn": task_arn,
        "networkInterfaceId": eni_id,
        "associationId": response["AssociationId"],
    }


def _network_interface_id(detail: dict) -> str | None:
    for attachment in detail.get("attachments", []):
        if attachment.get("type") != "ElasticNetworkInterface":
            continue
        for kv in attachment.get("details", []):
            if kv.get("name") == "networkInterfaceId":
                return kv.get("value")
    return None


def _network_interface_id_from_ecs(cluster_arn: str, task_arn: str) -> str | None:
    described = ecs.describe_tasks(cluster=cluster_arn, tasks=[task_arn])
    tasks = described.get("tasks", [])
    if not tasks:
        return None
    return _network_interface_id(tasks[0])
