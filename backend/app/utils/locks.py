"""Per-key locks for "check, lock the key, check again, create" (double-checked locking).

Used three times: the audio cache (key: cache key), indexing (document) and
summaries (document). Two concurrent requests for the same thing do the
expensive work once; requests for different things never wait for each other.
"""
import threading
from collections.abc import Callable, Hashable, Iterator
from contextlib import contextmanager
from typing import TypeVar

T = TypeVar("T")


class KeyedLock:
    """One lock per key, created on first use and dropped as soon as nobody holds
    or waits for it, so a lock per audio cache key doesn't grow memory forever.

        locks = KeyedLock()
        with locks(key):
            ...
    """

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._entries: dict[Hashable, list] = {}  # key -> [lock, holders + waiters]

    @contextmanager
    def __call__(self, key: Hashable) -> Iterator[None]:
        with self._guard:
            entry = self._entries.setdefault(key, [threading.Lock(), 0])
            entry[1] += 1
        try:
            with entry[0]:
                yield
        finally:
            with self._guard:
                entry[1] -= 1
                if not entry[1]:
                    del self._entries[key]

    def __len__(self) -> int:
        """Keys currently held or waited for (tests check nothing leaks)."""
        with self._guard:
            return len(self._entries)

    def get_or_create(self, key: Hashable, load: Callable[[], T | None], create: Callable[[], T]) -> T:
        """load() returns the stored value or None. Hit -> return at once, no lock.
        Miss -> lock the key, load again (another thread may have just created it),
        and only then create()."""
        if (value := load()) is not None:
            return value
        with self(key):
            if (value := load()) is not None:
                return value
            return create()
