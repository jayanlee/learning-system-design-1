# AWS edges

These are notes for creating the edges by hand. Nothing here has been created.

## CloudFront and S3

The browser uses one hostname. CloudFront serves the Vite build from a private S3 bucket (Origin Access Control). Paths `/api/auth*`, `/api/tasks*`, and `/api/notifications*` go to the ALB. Those API behaviors forward `Authorization` and `Cookie` and use CachingDisabled. A CloudFront function on the S3 behavior only rewrites client routes to `/index.html`. Do not attach that rewrite to the API behaviors.

## ALB alone

An Application Load Balancer sends `/api/auth*`, `/api/tasks*`, and `/api/notifications*` to the three ECS services. It checks `/health` and stops using a task that fails that check.

It does not check the JWT. It does not throttle per caller. Path rules are the feature.

## API Gateway alone

An HTTP API uses a VPC link to Cloud Map entries for the same ECS services. There is no load balancer. A starting stage throttle is 10 requests per second with a burst of 20.

An API Gateway JWT authorizer expects an OIDC issuer and a JWKS URL. The services sign HS256 tokens with a shared secret, so that authorizer does not accept the tokens this app issues. The services still check the token themselves. Login, refresh, and logout stay unauthenticated so a browser can obtain a token.

Cloud Map does not replace the ALB health check. A task that is up in Cloud Map can still be failing `/health` until ECS replaces it.

## Together

The HTTP API sends traffic to the ALB listener over the VPC link. Throttling sits at API Gateway. Target health sits at the ALB. The request takes an extra hop, costs more, and adds latency. Use this when you want both controls. Use one of them when you do not.

## EventBridge and SQS

The outbox in each service database is the record that an event happened. The relay calls `events:PutEvents` after that commit. Rules on the bus copy `UserRegistered` to the user queue and task events to the task queue. Each queue has a dead-letter queue after 5 receives.

EventBridge is routing. SQS is the buffer and the retry. Neither one is the source of the event.

## ECS and EKS

ECS Fargate runs the three APIs and the notification consumer. Tasks get public IPs in public subnets so they can pull images without a NAT gateway. The task security group does not accept traffic from the internet; only the ALB or the VPC link can reach port 8000.

The same consumer image is described again in [deploy/k8s/worker-deployment.yaml](../deploy/k8s/worker-deployment.yaml). An EKS control plane is a separate hourly charge even with no worker nodes. No cluster has been created.

## RDS

One instance, separate databases (`sd_auth`, `sd_task`, `sd_notify`, `sd_bus`). That is logical isolation. A failure of the instance takes all of them down. A single-AZ instance has no standby. Turning on Multi-AZ adds a standby and does not, by itself, prove failover. A restore has not been run. See [runbooks/backup-restore.md](runbooks/backup-restore.md).
