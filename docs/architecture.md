# Architecture notes

Request path: client -> Nginx edge proxy -> Kong API gateway -> two FastAPI instances -> PostgreSQL/Redis. Worker publishes transactional outbox events to Kafka. Prometheus scrapes metrics and Grafana visualizes them.

PostgreSQL is the source of truth for balances. Transfers use `Decimal`/`NUMERIC`, lock account rows in deterministic order, and write both ledger entries and an outbox event in the same database transaction. Redis is not the balance store.

Production gaps to close: authentication/authorization and ownership checks, strict idempotency concurrency handling, robust outbox claim/lease and Kafka acknowledgement handling, consumer deduplication, TLS, secrets manager, HA Postgres/Redis/Kafka, backups, alerting, WAF/DDoS controls, and security review.

Capacity is measured in requests/second, not registered users. Load-test gradually and monitor p95/p99 latency, errors, saturation, database pool waits, connection counts, and Kafka lag.
