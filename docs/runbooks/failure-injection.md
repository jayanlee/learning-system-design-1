# Failure injection

These are pytest cases. They run against local Postgres. They have not been run against AWS.

From each service directory: `.\.venv\Scripts\python.exe -m pytest`

| What breaks | Test | What you should see |
| --- | --- | --- |
| The bus rejects the publish after the user row commits | `auth-service/tests/test_outbox.py::test_failed_publish_is_retried_once` | The outbox row stays unpublished, `attempts` is 1, the lock is cleared, and a later relay pass sends one message |
| A second worker tries to publish a row another worker has leased | `test_lease_hides_a_row_from_a_second_worker` | No message until `locked_until` is in the past |
| The same task event is delivered twice | `notification-service/tests/test_consumer.py::test_duplicate_event_inserts_one_notification` and `test_bus_redelivery_is_still_one_notification` | One notification and one audit row |
| A message is received 5 times and never deleted | `test_message_moves_to_the_dead_letter_queue_after_five_receives` | The 6th receive moves it to `dead_letters` |
| Owner transfer commits on the destination shard and dies before the source shard | `task-service/tests/test_shards.py::test_transfer_crash_then_retry_leaves_one_visible_task` | Two visible copies, then one retry leaves a single visible task |
| The user row and the outbox row are not yet committed | `test_outbox_rolls_back_with_the_user` | Rolling back removes both |

SIGTERM handling is the relay and consumer threads stopping their loops, and the container `stopTimeout` of 30 seconds in Terraform. That shutdown path has not been killed in AWS.
