"""
Keep every request to data.rechtspraak.nl under its published rate limit.

data.rechtspraak.nl allows at most 10 requests per second and its firewall
blocks the client's IP when that is exceeded. It blocked the Airflow server
from 2026-11-09 after a citation backfill fetched per-ECLI metadata from one
thread per CPU with no delay. Importing this module routes the extractor
package's per-ECLI fetches through one process-wide limiter; call
``wait_for_slot()`` before any other request to the API.
"""

import functools
import os
import threading
import time

import rechtspraak_extractor.rechtspraak_metadata as rex_metadata

MAX_REQUESTS_PER_SECOND = float(os.getenv("RECHTSPRAAK_MAX_REQUESTS_PER_SECOND", "4"))

# Options for every get_rechtspraak_metadata call that may reach the live API.
# Fetch one ECLI at a time (the package otherwise starts one thread per CPU,
# which is what issue #31's 403s came from), and identify as a plain client:
# randomised browser headers from a server IP look like a bot to the firewall
# that rejects them.
POLITE_METADATA_OPTIONS = {"multi_threading": False, "_fake_headers": False}


class RateLimiter:
    """Space calls at least 1/per_second apart, across threads."""

    def __init__(self, per_second):
        self._interval = 1.0 / per_second
        self._lock = threading.Lock()
        self._next_slot = 0.0

    def wait(self):
        with self._lock:
            now = time.monotonic()
            slot = max(now, self._next_slot)
            self._next_slot = slot + self._interval
        if slot > now:
            time.sleep(slot - now)


_limiter = RateLimiter(MAX_REQUESTS_PER_SECOND)


def wait_for_slot():
    _limiter.wait()


def rate_limited(fetch):
    @functools.wraps(fetch)
    def wrapper(*args, **kwargs):
        wait_for_slot()
        return fetch(*args, **kwargs)

    wrapper.rate_limited = True
    return wrapper


# get_data_from_api looks extract_data_from_xml up in its module on every
# call, so replacing the module attribute throttles every per-ECLI request.
if not getattr(rex_metadata.extract_data_from_xml, "rate_limited", False):
    rex_metadata.extract_data_from_xml = rate_limited(rex_metadata.extract_data_from_xml)
