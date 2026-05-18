"""
Spec §13 — LRU OCR cache.

TTL=2s, max 500 entries.
Key = (roi_hash, preprocess_hash, allow_list_hash).
"""

import hashlib
import threading
import time
from collections import OrderedDict


CACHE_TTL_S = 2.0
CACHE_MAX_ENTRIES = 500


class OcrCache:
    """LRU cache for OCR results with TTL eviction."""

    def __init__(self, ttl_s: float = CACHE_TTL_S, max_entries: int = CACHE_MAX_ENTRIES):
        self._ttl = ttl_s
        self._max = max_entries
        self._store: OrderedDict[str, tuple[float, list]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def _make_key(self, roi_hash: str, preprocess_hash: str,
                  allow_list_hash: str = "") -> str:
        raw = f"{roi_hash}|{preprocess_hash}|{allow_list_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, roi_hash: str, preprocess_hash: str,
            allow_list: str | None = None) -> list | None:
        allow_hash = _hash_str(allow_list) if allow_list else ""
        key = self._make_key(roi_hash, preprocess_hash, allow_hash)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            ts, results = entry
            if time.time() - ts > self._ttl:
                del self._store[key]
                self._misses += 1
                return None
            # Move to end (LRU)
            self._store.move_to_end(key)
            self._hits += 1
            return results

    def put(self, roi_hash: str, preprocess_hash: str,
            allow_list: str | None, results: list):
        allow_hash = _hash_str(allow_list) if allow_list else ""
        key = self._make_key(roi_hash, preprocess_hash, allow_hash)
        with self._lock:
            self._store[key] = (time.time(), results)
            self._store.move_to_end(key)
            # Evict oldest if over capacity
            while len(self._store) > self._max:
                self._store.popitem(last=False)

    def invalidate(self, roi_hash: str | None = None):
        with self._lock:
            if roi_hash is None:
                self._store.clear()
            else:
                keys_to_del = [k for k in self._store if roi_hash in k]
                for k in keys_to_del:
                    del self._store[k]

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        if total == 0:
            return 0.0
        return self._hits / total

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._store)

    def stats(self) -> dict:
        return {
            "size": self.size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self.hit_rate,
            "max_entries": self._max,
            "ttl_s": self._ttl,
        }


def _hash_str(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]
