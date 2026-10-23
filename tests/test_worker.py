
from app.worker import delivery_callback, enqueue_event


class FakeMessage:
    def topic(self):
        return "payment-events"

    def partition(self):
        return 0


class FakeEvent:
    id = 17
    aggregate_id = "ACC100001"
    payload = {"event": "payment.completed", "amount": 1}


class FakeProducer:
    def __init__(self):
        self.messages = []

    def produce(self, **kwargs):
        self.messages.append(kwargs)


def test_delivery_callback_records_success(capsys):
    results = {}
    callback = delivery_callback(results, 17)

    callback(None, FakeMessage())

    assert results[17] is True
    assert "Kafka delivery confirmed" in capsys.readouterr().out


def test_delivery_callback_records_failure(capsys):
    results = {}
    callback = delivery_callback(results, 17)

    callback(RuntimeError("Kafka unavailable"), None)

    assert results[17] is False
    assert "Kafka delivery failed" in capsys.readouterr().out


def test_enqueue_event_enqueues_one_message():
    producer = FakeProducer()
    event = FakeEvent()
    results = {}

    enqueue_event(producer, event, results, "payment-events")

    assert len(producer.messages) == 1

    message = producer.messages[0]
    assert message["topic"] == "payment-events"
    assert message["key"] == "ACC100001"
    assert '"amount": 1' in message["value"]
    assert callable(message["callback"])
    assert results == {}
