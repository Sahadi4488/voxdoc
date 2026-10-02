import threading
import time

import pytest

from app.utils.locks import KeyedLock


def run_together(n, target):
    threads = [threading.Thread(target=target) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def test_same_key_creates_once():
    locks, store, created = KeyedLock(), {}, []

    def create():
        time.sleep(0.1)  # long enough for every thread to miss the first check
        created.append(1)
        store["k"] = "value"
        return "value"

    results = []
    run_together(5, lambda: results.append(locks.get_or_create("k", lambda: store.get("k"), create)))
    assert created == [1] and results == ["value"] * 5


def test_different_keys_do_not_wait_for_each_other():
    locks = KeyedLock()
    holding, release = threading.Event(), threading.Event()

    def hold_a():
        with locks("a"):
            holding.set()
            release.wait(5)

    t = threading.Thread(target=hold_a)
    t.start()
    holding.wait(5)
    started = time.perf_counter()
    with locks("b"):  # would block until release if all keys shared one lock
        waited = time.perf_counter() - started
    release.set()
    t.join()
    assert waited < 0.5


def test_locks_are_dropped_after_use():
    locks = KeyedLock()
    for key in range(100):
        locks.get_or_create(key, lambda: None, lambda: "x")
    assert len(locks) == 0  # no lock per key left behind forever


def test_failed_create_releases_the_lock():
    locks = KeyedLock()

    def boom():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        locks.get_or_create("k", lambda: None, boom)
    assert len(locks) == 0
    assert locks.get_or_create("k", lambda: None, lambda: "second try") == "second try"
