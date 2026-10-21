# Local run

The primary path is in the root [README](../../README.md): Postgres on localhost, three virtualenvs, Vite.

Tests create `sd_auth`, `sd_notify`, `sd_task_0`, `sd_task_1`, and `sd_bus` if they are missing. They do not use Docker.

`docker compose up --build` is optional. It uses host port 5433 so it does not take the Postgres already bound to 5432. The UI is still `npm run dev`.
