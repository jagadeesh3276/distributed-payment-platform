
import json
import time
from datetime import datetime, timezone

from confluent_kafka import Producer
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import OutboxEvent


BATCH_SIZE = 100
FLUSH_TIMEOUT_SECONDS = 10
POLL_INTERVAL_SECONDS = 1
ERROR_RETRY_SECONDS = 2


def delivery_callback(delivery_results, event_id):
    """Record Kafka's delivery result for an outbox event."""

    def callback(err, message):
        if err is not None:
            delivery_results[event_id] = False
            print(
                f"Kafka delivery failed for outbox event {event_id}: {err}",
                flush=True,
            )
        else:
            delivery_results[event_id] = True
            print(
                f"Kafka delivery confirmed: event_id={event_id}, "
                f"topic={message.topic()}, partition={message.partition()}",
                flush=True,
            )

    return callback

def enqueue_event(producer, event, delivery_results, topic):
    """Enqueue one outbox event and record its eventual delivery result."""
    producer.produce(
        topic=topic,
        key=event.aggregate_id,
        value=json.dumps(event.payload),
        callback=delivery_callback(delivery_results, event.id),
    )
def main():
    producer = Producer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "enable.idempotence": True,
            "acks": "all",
            "retries": 5,
            "max.in.flight.requests.per.connection": 5,
        }
    )

    print("Kafka outbox worker started", flush=True)

    while True:
        try:
            with SessionLocal() as db:
                events = db.scalars(
                    select(OutboxEvent)
                    .where(OutboxEvent.published_at.is_(None))
                    .order_by(OutboxEvent.id)
                    .limit(BATCH_SIZE)
                    .with_for_update(skip_locked=True)
                ).all()

                if not events:
                    db.rollback()
                    time.sleep(POLL_INTERVAL_SECONDS)
                    continue

                delivery_results = {}

                for event in events:
                    try:
                        producer.produce(
                            topic=settings.kafka_topic,
                            key=event.aggregate_id,
                            value=json.dumps(event.payload),
                            callback=delivery_callback(
                                delivery_results, event.id
                            ),
                        )
                    except Exception as exc:
                        print(
                            f"Could not enqueue event {event.id}: {exc}",
                            flush=True,
                        )

                remaining = producer.flush(FLUSH_TIMEOUT_SECONDS)

                if remaining:
                    print(
                        f"Kafka flush timed out; {remaining} "
                        "message(s) remain queued",
                        flush=True,
                    )

                published_count = 0

                for event in events:
                    if delivery_results.get(event.id) is True:
                        event.published_at = datetime.now(timezone.utc)
                        published_count += 1

                if published_count:
                    db.commit()
                    print(
                        f"Marked {published_count} event(s) as published",
                        flush=True,
                    )
                else:
                    db.rollback()

        except Exception as exc:
            print(f"Outbox worker error: {exc}", flush=True)
            time.sleep(ERROR_RETRY_SECONDS)

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
