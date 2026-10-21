# Schema

Each database is owned by one service. There are no foreign keys across databases.

## sd_auth

`users`

- `id` uuid primary key
- `name` text
- `email` unique
- `password_hash`
- `created_at`

`refresh_tokens`

- `id` uuid primary key
- `user_id` references `users.id` on delete cascade
- `token_hash` unique SHA-256
- `expires_at`, `revoked_at`, `created_at`

`outbox` (phase 2)

- `id` uuid primary key
- `event_id` uuid unique, the consumer idempotency key
- `event_type`
- `payload` jsonb
- `created_at`
- `locked_by`, `locked_until` lease
- `attempts`, `next_attempt_at`
- `published_at` null until the relay has copied the row to the bus

## sd_task

One database for a normal local run (`sd_task`). Tests use two databases, `sd_task_0` and `sd_task_1`, with the same tables. The shard key is `owner_id`. A cloud deploy is one shard until `TASK_DATABASE_URLS` lists more than one database URL.

`user_directory`

- `user_id` uuid primary key
- `email` unique
- `name`
- `synced_at`

This is a copy of account fields the task service needs. Auth is the source. The copy lags until `UserRegistered` is consumed. Creating a task also upserts the caller from the JWT.

`tasks`

- `id` uuid primary key
- `owner_id`, `assignee_id` nullable
- `title`, `description`, `status`
- `version` integer, starts at 1
- `created_at`, `updated_at`
- `moved_at` nullable (phase 3). A moved row stays for the transfer retry and is hidden from reads.

`idempotency_keys`

- primary key (`user_id`, `key`)
- `request_hash`, `response_status`, `response_body`, `created_at`

`outbox` and `processed_events` (phase 2), same outbox shape as auth. `processed_events.event_id` is the primary key for user events this service has applied.

## sd_notify

`notifications`

- `id` uuid primary key
- `user_id`, `task_id` nullable
- `type`, `payload` jsonb
- `read_at` nullable, `created_at`

`processed_events` (phase 2)

- `event_id` uuid primary key
- `processed_at`

`audit_log` (phase 2)

- `id` uuid primary key
- `event_id` unique
- `action`, `actor_id`, `task_id`, `payload`, `created_at`

## sd_bus (local stand-in for SQS)

Not a service database. Created by the bus client.

`messages`

- `id` uuid primary key
- `queue_name`
- `body` jsonb
- `receive_count`
- `visible_at`, `created_at`

`dead_letters`

- `id`, `queue_name`, `body`, `receive_count`, `created_at`

A message moves here when a receive would make `receive_count` greater than 5.
