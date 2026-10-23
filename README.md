# Distributed Payment Platform — Learning Scaffold

FastAPI + PostgreSQL + Redis + Kafka + Kong API Gateway + Nginx edge proxy + Prometheus/Grafana + Locust.

**Important:** This is a development and learning scaffold, not a certified production payment processor. Do not use real money or customer data. No architecture can guarantee “millions of requests” without workload-specific testing and appropriately provisioned infrastructure.

## Start locally
1. Install Docker Desktop with Compose v2.
2. Copy `.env.example` to `.env`; change the development passwords.
3. `docker compose up --build -d`
4. Run migrations: `docker compose run --rm api-1 alembic upgrade head`
5. `docker compose restart api-1 api-2 worker`

Endpoints:
- API via Nginx: http://localhost:8080
- Kong directly: http://localhost:8000
- Swagger: http://localhost:8080/docs
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- Locust UI: `docker compose --profile loadtest run --rm --service-ports locust` then http://localhost:8089

## Example (PowerShell)
Create accounts:
`curl.exe -X POST http://localhost:8080/accounts -H "Content-Type: application/json" -d "{\"account_number\":\"ACC10001\",\"owner_id\":\"USER1001\",\"currency\":\"INR\"}"`
`curl.exe -X POST http://localhost:8080/accounts -H "Content-Type: application/json" -d "{\"account_number\":\"ACC10002\",\"owner_id\":\"USER1002\",\"currency\":\"INR\"}"`
Deposit:
`curl.exe -X POST http://localhost:8080/accounts/ACC10001/deposits -H "Content-Type: application/json" -H "Idempotency-Key: dep-001" -d "{\"amount\":\"1000.00\"}"`
Transfer:
`curl.exe -X POST http://localhost:8080/transfers -H "Content-Type: application/json" -H "Idempotency-Key: tr-001" -d "{\"source_account\":\"ACC10001\",\"destination_account\":\"ACC10002\",\"amount\":\"125.00\"}"`

## Architecture
Nginx -> Kong gateway -> two FastAPI instances -> PostgreSQL and Redis. A transactional outbox worker publishes committed events to Kafka. Prometheus scrapes API metrics; Grafana reads Prometheus; Locust generates test traffic.

PostgreSQL is the source of truth for balances and ledger. Money uses `Decimal` / `NUMERIC(18,2)`. Transfers lock account rows in deterministic order and write both ledger entries and the outbox event in one transaction. Kafka publishing happens asynchronously.

## Load testing
Start low and increase users/rate gradually. Measure p95/p99 latency, error rate, CPU, memory, DB pool waits, DB connections, Redis errors, Kafka lag and queue depth. “Millions of users” is not a capacity metric: define requests/second and workload mix. Production needs TLS, strong authn/authz, ownership enforcement, secrets management, HA databases/brokers, backups, alerting, consumer deduplication, recovery drills and independent security review.
