# Task platform

Auth, tasks, and notifications as three Python services with separate Postgres databases. Locally the React UI talks to them through the Vite dev server. In AWS the browser talks to one CloudFront hostname: static files from S3, `/api/*` to an ALB in front of ECS.

The lesson in this repo is a write that has to land in more than one database. See [docs/architecture.md](docs/architecture.md), [docs/schema.md](docs/schema.md), and [docs/STATUS.md](docs/STATUS.md). What is tested is listed there. AWS is created by hand. There is no Terraform in this repo.

Sister app: `c:\Work\learning\zifo`. This repo uses different ports and database names so both can run on one machine.

## Run locally

Postgres is already running. From each service directory, use its own virtualenv.

```powershell
cd auth-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DATABASE_URL = "postgresql+psycopg://postgres@localhost:5432/sd_auth"
$env:JWT_SECRET = "dev-only-change-me"
alembic upgrade head
uvicorn app.main:app --port 8090
```

```powershell
cd task-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DATABASE_URL = "postgresql+psycopg://postgres@localhost:5432/sd_task"
$env:JWT_SECRET = "dev-only-change-me"
alembic upgrade head
uvicorn app.main:app --port 8091
```

```powershell
cd notification-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DATABASE_URL = "postgresql+psycopg://postgres@localhost:5432/sd_notify"
$env:JWT_SECRET = "dev-only-change-me"
alembic upgrade head
uvicorn app.main:app --port 8092
```

```powershell
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5174. Vite proxies `/api/auth`, `/api/tasks`, and `/api/notifications`.

Create the databases once if they are missing:

```powershell
psql -U postgres -c "CREATE DATABASE sd_auth"
psql -U postgres -c "CREATE DATABASE sd_task"
psql -U postgres -c "CREATE DATABASE sd_notify"
```

## Tests

From each service directory, with the same `DATABASE_URL` and `JWT_SECRET` as above (tests also set these themselves):

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Tests create `sd_auth`, `sd_notify`, `sd_task_0`, `sd_task_1`, and `sd_bus` if they are missing. Task tests use two databases so shard behavior has something to run against. A normal local run uses one task database, `sd_task`.

## Optional containers

`docker compose up --build` starts Postgres on host port 5433 and the three APIs. It is not required. The UI is still `npm run dev`.

## AWS

The product URL is CloudFront, same split as zifo.

```text
Browser
  https://<cloudfront>
    /                    Vite build in a private S3 bucket
    /api/auth/*          ALB → ECS auth
    /api/tasks/*         ALB → ECS task
    /api/notifications/* ALB → ECS notification
```

React still calls relative `/api/...` paths. The Vite proxy is only for localhost.

GitHub Actions on `main` builds and pushes the three images to ECR (`task-platform/auth`, `task-platform/task`, `task-platform/notification`) and syncs `frontend/dist` to S3. ECS rolling deploys are added after those services exist. The workflows need repository secrets `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, and `S3_BUCKET`. They do not read `JWT_SECRET` or database URLs.

Notes on the edges, the bus, and a rough cost are in [docs/aws.md](docs/aws.md) and [docs/cost.md](docs/cost.md). The notification worker manifest is [deploy/k8s/worker-deployment.yaml](deploy/k8s/worker-deployment.yaml). A cluster has not been created.

