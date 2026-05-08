from __future__ import annotations

import threading
from typing import Any, Dict, List, Tuple


class InMemoryStateStore:
    """Thread-safe, versioned in-memory state store.

    Features:
    - get/set with global monotonic version number
    - compare-and-set (CAS) for safe concurrent updates
    - event history (version, key, value)
    - snapshot and restore by version
    """

    def __init__(self) -> None:
        self._store: Dict[str, Any] = {}
        self._version: int = 0
        self._history: List[Tuple[int, str, Any]] = []
        self._lock = threading.RLock()

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._store.get(key, default)

    def set(self, key: str, value: Any) -> int:
        """Set key to value and return new global version."""
        with self._lock:
            self._version += 1
            self._store[key] = value
            self._history.append((self._version, key, value))
            return self._version

    def cas(self, key: str, expected_version: int, value: Any) -> Tuple[bool, int]:
        """Compare-and-set: if the last write-version for `key` equals expected_version,
        set to `value` and return (True, new_version). Otherwise return (False, current_version).
        If the key has never been written, expected_version should be 0.
        """
        with self._lock:
            # find last version for key
            last = 0
            for v, k, _ in reversed(self._history):
                if k == key:
                    last = v
                    break

            if last != expected_version:
                return False, last

            self._version += 1
            self._store[key] = value
            self._history.append((self._version, key, value))
            return True, self._version

    def version(self) -> int:
        with self._lock:
            return self._version

    def snapshot(self) -> Tuple[int, Dict[str, Any]]:
        """Return (version, shallow copy of store)."""
        with self._lock:
            return self._version, dict(self._store)

    def history(self) -> List[Tuple[int, str, Any]]:
        with self._lock:
            return list(self._history)

    def restore(self, version: int) -> None:
        """Restore store to the state at given version. Raises ValueError if version invalid."""
        with self._lock:
            if version < 0 or version > self._version:
                raise ValueError("invalid version")

            # rebuild store from history up to version
            new_store: Dict[str, Any] = {}
            for v, k, val in self._history:
                if v > version:
                    break
                new_store[k] = val

            # truncate history
            self._history = [(v, k, val) for (v, k, val) in self._history if v <= version]
            self._store = new_store
            self._version = version

    def keys(self) -> List[str]:
        with self._lock:
            return list(self._store.keys())
