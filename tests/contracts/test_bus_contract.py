"""Контракт шины: его проходит любая будущая шина (внутри процесса или внешняя)."""

from core.bus import ALL, LocalBus


def test_publish_reaches_topic_and_wildcard_subscribers_in_order():
    bus, got = LocalBus(), []
    bus.subscribe("event", lambda t, p: got.append(("a", p)))
    bus.subscribe("event", lambda t, p: got.append(("b", p)))
    bus.subscribe(ALL, lambda t, p: got.append(("all", t)))
    bus.subscribe("other", lambda t, p: got.append(("no", p)))
    bus.publish("event", 1)
    assert got == [("a", 1), ("b", 1), ("all", "event")]


def test_broken_subscriber_does_not_stop_others():
    bus, got = LocalBus(), []

    def broken(t, p):
        raise RuntimeError("boom")

    bus.subscribe("event", broken)
    bus.subscribe("event", lambda t, p: got.append(p))
    bus.publish("event", 7)
    assert got == [7]
    assert bus.errors and bus.errors[0][0] == "event"
