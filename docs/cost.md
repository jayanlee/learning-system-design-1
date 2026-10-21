# Cost estimate

These are rough monthly figures for `ap-southeast-2` at a small steady state, one task per service, little traffic. They are not a quote. Prices move. Nothing in this list has been created, so none of it is a bill from this repo.

| Piece | Estimate | Note |
| --- | --- | --- |
| ALB | $20–25 | Hourly charge plus a small LCU cost at demo traffic |
| Fargate, four tasks at 0.25 vCPU and 0.5 GB | $35–45 | Auth, task, notification API, worker |
| Public IPv4 | $15–20 | ALB addresses plus one address per task with a public IP |
| RDS `db.t4g.micro`, single-AZ | $15–20 | Lower during a free-tier year on a new account |
| RDS Multi-AZ | about 2× the database line | Only if you turn on a standby |
| Secrets Manager, 4 secrets | about $2 | |
| CloudWatch logs, 14 days, light use | $5–10 | |
| API Gateway HTTP, SQS, EventBridge | under $5 | At demo volume |
| EKS control plane | about $73 | Only if you create a cluster. Nodes are extra |
| NAT gateway | not in the plan | Avoided by using public subnets |

A small manual layout (ALB, no Multi-AZ, no EKS) is on the order of **$90–120 per month**. Adding API Gateway in front of the ALB adds a few dollars at this volume, not a new large line. Adding EKS adds the control-plane fee before any pod is scheduled.
