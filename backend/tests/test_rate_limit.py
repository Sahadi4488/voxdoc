import threading

import pytest

from app.utils.rate_limit import SlidingWindowLimiter


class FakeClock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture()
def clock():
    return FakeClock()


def test_eleventh_request_is_blocked_with_the_right_wait(clock):
    limiter = SlidingWindowLimiter(limit=10, window_s=600, clock=clock)
    for i in range(10):
        clock.t = 1000 + i * 30  # one request every 30 s
        assert limiter.check("1.2.3.4") == (True, 0)
    clock.t = 1300
    # The oldest request (t=1000) leaves the window at t=1600: 300 s from now
    assert limiter.check("1.2.3.4") == (False, 300)


def test_allowed_again_once_the_oldest_request_leaves_the_window(clock):
    limiter = SlidingWindowLimiter(limit=10, window_s=600, clock=clock)
    for _ in range(10):
        limiter.check("a")
    clock.t += 599
    assert limiter.check("a") == (False, 1)
    clock.t += 1
    assert limiter.check("a") == (True, 0)


def test_refused_requests_do_not_extend_the_wait(clock):
    limiter = SlidingWindowLimiter(limit=2, window_s=60, clock=clock)
    limiter.check("a"), limiter.check("a")
    for _ in range(50):
        clock.t += 1
        assert not limiter.check("a")[0]
    clock.t += 10  # 60 s after the first two
    assert limiter.check("a") == (True, 0)


def test_a_different_key_is_unaffected(clock):
    limiter = SlidingWindowLimiter(limit=10, window_s=600, clock=clock)
    for _ in range(10):
        limiter.check("busy visitor")
    assert not limiter.check("busy visitor")[0]
    assert limiter.check("someone else") == (True, 0)


def test_keys_of_visitors_who_left_are_deleted(clock):
    limiter = SlidingWindowLimiter(limit=10, window_s=600, clock=clock)
    for ip in range(500):
        limiter.check(f"10.0.0.{ip}")
    assert len(limiter) == 500
    clock.t += 601  # every request has expired; the next check sweeps
    limiter.check("new visitor")
    assert len(limiter) == 1


def test_concurrent_requests_never_exceed_the_limit(clock):
    limiter = SlidingWindowLimiter(limit=10, window_s=600, clock=clock)
    allowed = []
    threads = [threading.Thread(target=lambda: allowed.append(limiter.check("a")[0])) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert allowed.count(True) == 10


def test_limit_must_be_positive():
    with pytest.raises(ValueError):
        SlidingWindowLimiter(limit=0)
