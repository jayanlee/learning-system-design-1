# Backup and restore

This runbook has not been executed. Automated backups are something you turn on in RDS. They are not evidence that a restore works. A single-AZ instance has no standby.

When you want to practice a restore:

1. In RDS, note the latest automated snapshot or take a manual snapshot of the instance.
2. Restore that snapshot to a new instance. Do not replace the original.
3. Create the application databases if the snapshot predates them, using [scripts/databases.sql](../../scripts/databases.sql).
4. Point a scratch task's database URL at the new instance. Do not point the running services at it until you mean to.
5. Run `alembic upgrade head` against the new instance.
6. Register a user and create a task against that scratch instance.
7. Delete the scratch instance when you are finished. Deleting the original instance is a separate decision.

Write down the snapshot id, the new instance id, and whether login worked. Until that note exists, restore is not tested.
