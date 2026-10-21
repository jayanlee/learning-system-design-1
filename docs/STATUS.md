# Status

Labels mean what they say. **Implemented** is in this repo. **Tested** has an automated check that has been run here. **Not built** is absent, or present only as a manifest or a runbook that has not been executed.

High availability and production readiness are not claimed. No AWS resources were created.

| Area | Label | Evidence |
| --- | --- | --- |
| Auth register, login, refresh rotation, logout, me, lookup | Tested | `auth-service` pytest, 10 passed |
| Task CRUD, assign, status, version, idempotency key, write rate limit | Tested | `task-service` pytest, 10 passed |
| `/health` and `/ready` | Tested | Included in those runs |
| Notification list and mark-read | Tested | `notification-service` pytest, 5 passed |
| Transactional outbox, lease, backoff, one retry after a failed publish | Tested | `tests/test_outbox.py` |
| Local bus, duplicate delivery, DLQ after 5 receives | Tested | `tests/test_consumer.py` |
| User directory filled from `UserRegistered` | Tested | `tests/test_events.py` |
| Two task shards, scatter-gather list, owner-transfer crash then retry | Tested | `tests/test_shards.py` |
| React UI for register, login, tasks, assign, transfer, notifications | Tested | Browser on `http://127.0.0.1:5174`: register, create a task, assign returned 409 and the message stayed on screen, status changed to in progress, notifications page showed the lag note and an empty list. Transfer was not clicked in the browser; that path is covered by `tests/test_shards.py` |
| Dockerfiles and optional Compose | Implemented | Images were not built here |
| AWS resources (ECS, ALB, API Gateway, RDS, EventBridge, SQS and DLQ, CloudWatch, Secrets Manager, IAM) | Not built | Terraform was removed. These are created by hand. None have been created |
| In-memory rate limit across more than one process | Not built | A shared limiter is not built. A gateway throttle would be set by hand |
| HS256 tokens checked by an API Gateway JWT authorizer | Not built | That authorizer expects OIDC. Services check the token themselves |
| Multi-AZ, autoscaling observed, backup restore | Not built | A restore runbook only. No standby is configured |
| EKS cluster | Not built | Manifest is in `deploy/k8s`. No cluster has been created |
| Graceful shutdown under a real SIGTERM | Implemented | Thread stop and `stopTimeout` are in the code. Not killed in a running deploy |
