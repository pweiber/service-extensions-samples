# Copyright 2026 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Bearer token fetcher for Vertex AI calls.

Uses the GCE/Cloud Run metadata server to mint short-lived OAuth tokens for the
service account attached to the runtime. Tokens are cached in-process and
refreshed before expiry.
"""

import logging
import os
import threading
import time
from typing import Optional

import requests

_METADATA_URL = (
    "http://metadata.google.internal/computeMetadata/v1/"
    "instance/service-accounts/default/token"
)
_METADATA_HEADERS = {"Metadata-Flavor": "Google"}
_REFRESH_MARGIN_SECONDS = 300


class _TokenCache:
    """Thread-safe access token cache with proactive refresh."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._token: Optional[str] = None
        self._expires_at: float = 0.0

    def get(self) -> str:
        now = time.time()
        with self._lock:
            if self._token and now < self._expires_at - _REFRESH_MARGIN_SECONDS:
                return self._token
            self._token, self._expires_at = _fetch_token()
            return self._token


def _fetch_token() -> tuple[str, float]:
    override = os.getenv("VERTEX_ACCESS_TOKEN")
    if override:
        return override, time.time() + 3600
    resp = requests.get(_METADATA_URL, headers=_METADATA_HEADERS, timeout=2)
    resp.raise_for_status()
    payload = resp.json()
    token = payload["access_token"]
    expires_in = int(payload.get("expires_in", 3600))
    logging.info("Refreshed Vertex AI access token (expires in %ds)", expires_in)
    return token, time.time() + expires_in


_cache = _TokenCache()


def fetch_vertex_token() -> str:
    """Return a valid Bearer token for Vertex AI.

    Honors the VERTEX_ACCESS_TOKEN env var as an override (useful for local
    testing with a `gcloud auth print-access-token` value).
    """
    return _cache.get()
