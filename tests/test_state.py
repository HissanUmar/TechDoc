import threading

from agentic_framework.state import InMemoryStateStore


def test_set_get_version_and_history():
    s = InMemoryStateStore()
    v1 = s.set("a", 1)
    assert v1 == 1
    v2 = s.set("b", 2)
    assert v2 == 2
    assert s.get("a") == 1
    ver, snap = s.snapshot()
    assert ver == 2
    assert snap == {"a": 1, "b": 2}
    hist = s.history()
    assert hist[0] == (1, "a", 1)
    assert hist[1] == (2, "b", 2)


def test_cas_success_and_failure():
    s = InMemoryStateStore()
    v1 = s.set("x", 10)
    ok, v2 = s.cas("x", v1, 11)
    assert ok is True
    assert s.get("x") == 11

    # CAS with wrong expected version fails
    ok2, cur = s.cas("x", v1, 12)
    assert ok2 is False
    assert cur == v2


def test_restore_snapshot():
    s = InMemoryStateStore()
    s.set("k", 1)
    s.set("k", 2)
    s.set("o", 3)
    ver = s.version()
    assert ver == 3
    s.restore(2)
    assert s.version() == 2
    assert s.get("k") == 2
    assert "o" not in s.keys()


def test_thread_safety():
    s = InMemoryStateStore()

    def writer(i):
        for _ in range(10):
            s.set("k", i)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # last writer's value should be present and version should be > 0
    assert s.version() > 0
    assert s.get("k") in [0, 1, 2, 3]
