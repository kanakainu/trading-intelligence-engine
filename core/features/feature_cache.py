"""Feature Cache — Caches FeatureSnapshot per symbol per scan to avoid recomputation."""
import time
from typing import Dict, Optional
from threading import Lock

from core.features.feature_models import FeatureSnapshot, FeatureInputs
from core.features.feature_engine import FeatureEngine


class FeatureCache:
    """
    Thread-safe cache for FeatureSnapshot.
    - One entry per symbol per scan_id
    - TTL-based expiry (default: 15s, slightly > scan interval)
    - Invalidates on new scan
    """

    def __init__(self, ttl_seconds: float = 15.0):
        self._cache: Dict[str, tuple[FeatureSnapshot, float]] = {}  # key -> (snapshot, timestamp)
        self._ttl = ttl_seconds
        self._lock = Lock()
        self._engine = FeatureEngine()

    def get_or_compute(self, inputs: FeatureInputs) -> FeatureSnapshot:
        """Get cached snapshot or compute new one."""
        key = self._make_key(inputs)

        with self._lock:
            # Check cache
            if key in self._cache:
                snapshot, cached_at = self._cache[key]
                if time.time() - cached_at < self._ttl:
                    return snapshot

            # Compute new
            snapshot = self._engine.compute(inputs)
            self._cache[key] = (snapshot, time.time())
            self._cleanup_expired()
            return snapshot

    def get(self, symbol: str, scan_id: str) -> Optional[FeatureSnapshot]:
        """Get cached snapshot by symbol and scan_id."""
        key = f"{symbol}:{scan_id}"
        with self._lock:
            if key in self._cache:
                snapshot, cached_at = self._cache[key]
                if time.time() - cached_at < self._ttl:
                    return snapshot
        return None

    def invalidate(self, symbol: str) -> None:
        """Invalidate all entries for a symbol."""
        with self._lock:
            keys_to_remove = [k for k in self._cache if k.startswith(f"{symbol}:")]
            for k in keys_to_remove:
                del self._cache[k]

    def clear(self) -> None:
        """Clear entire cache."""
        with self._lock:
            self._cache.clear()

    def _make_key(self, inputs: FeatureInputs) -> str:
        """Generate cache key from inputs."""
        # Use symbol + timestamp rounded to scan interval (10s)
        ts_bucket = int(time.time() / 10) * 10
        return f"{inputs.symbol}:{ts_bucket}"

    def _cleanup_expired(self) -> None:
        """Remove expired entries."""
        now = time.time()
        expired = [k for k, (_, t) in self._cache.items() if now - t >= self._ttl]
        for k in expired:
            del self._cache[k]

    def stats(self) -> Dict[str, int]:
        """Cache statistics."""
        with self._lock:
            return {
                "entries": len(self._cache),
                "symbols": len(set(k.split(":")[0] for k in self._cache)),
            }


# Global cache instance (singleton pattern)
_global_cache: Optional[FeatureCache] = None


def get_feature_cache(ttl_seconds: float = 15.0) -> FeatureCache:
    """Get or create global feature cache."""
    global _global_cache
    if _global_cache is None:
        _global_cache = FeatureCache(ttl_seconds)
    return _global_cache


def compute_features(inputs: FeatureInputs) -> FeatureSnapshot:
    """Convenience function: compute features using global cache."""
    cache = get_feature_cache()
    return cache.get_or_compute(inputs)