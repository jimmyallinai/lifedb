"""Rate limiter with RANDOM intervals.

House rule (learned the hard way): fixed-interval polling is a bot
fingerprint and gets accounts flagged. Every delay is drawn uniformly at
random from [min_s, max_s]; there is deliberately no fixed-interval mode.
On HTTP 403 a platform run stops immediately (StopOn403) instead of
retrying inside the same session.
"""

from __future__ import annotations

import random
import time


class PlatformBlocked(Exception):
    """Platform answered 403 / risk-control: stop this run, do not retry."""


def raise_for_status(status: int) -> None:
    if status == 403:
        raise PlatformBlocked("platform returned 403; stopping this run")


class RateLimiter:
    def __init__(self, min_s: float = 1.0, max_s: float = 3.0,
                 rng: random.Random | None = None):
        if not (0 <= min_s < max_s):
            raise ValueError("need 0 <= min_s < max_s (random interval required)")
        self.min_s = float(min_s)
        self.max_s = float(max_s)
        self._rng = rng or random.Random()

    def next_delay(self) -> float:
        return self._rng.uniform(self.min_s, self.max_s)

    def wait(self) -> float:
        delay = self.next_delay()
        time.sleep(delay)
        return delay
