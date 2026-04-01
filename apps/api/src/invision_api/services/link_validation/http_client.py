from __future__ import annotations

import random
import time
from urllib.parse import urlsplit

import httpx

from invision_api.services.link_validation.config import LinkValidationConfig
from invision_api.services.link_validation.types import HttpProbeResult

_CLOUD_HOSTS = {
    "drive.google.com",
    "docs.google.com",
    "www.dropbox.com",
    "dropbox.com",
    "db.tt",
    "onedrive.live.com",
    "1drv.ms",
}

_BODY_SNIPPET_MAX = 8192


def _is_cloud_url(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in _CLOUD_HOSTS)


class HttpProbeClient:
    def __init__(self, config: LinkValidationConfig):
        self._config = config

    def probe(self, url: str) -> HttpProbeResult:
        timeout = httpx.Timeout(connect=self._config.connect_timeout_sec, read=self._config.read_timeout_sec, write=5.0, pool=5.0)
        last_error: str | None = None
        needs_body = _is_cloud_url(url)

        for attempt in range(1, self._config.retry_attempts + 1):
            started = time.perf_counter()
            try:
                with httpx.Client(
                    follow_redirects=True,
                    timeout=timeout,
                    max_redirects=self._config.max_redirects,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; invision-link-validator/1.0)"},
                ) as client:
                    if needs_body:
                        response = client.get(url)
                    else:
                        response = client.head(url)
                        if response.status_code in {405, 403, 400}:
                            response = client.get(url, headers={"Range": "bytes=0-0"})

                elapsed_ms = int((time.perf_counter() - started) * 1000)
                history = response.history or []
                content_length_header = response.headers.get("content-length")
                content_length = int(content_length_header) if content_length_header and content_length_header.isdigit() else None

                body_snippet: str | None = None
                if needs_body:
                    ct = (response.headers.get("content-type") or "").lower()
                    if "text/html" in ct:
                        body_snippet = response.text[:_BODY_SNIPPET_MAX]

                return HttpProbeResult(
                    final_url=str(response.url),
                    status_code=response.status_code,
                    content_type=response.headers.get("content-type"),
                    content_length=content_length,
                    redirected=bool(history),
                    redirect_count=len(history),
                    response_time_ms=elapsed_ms,
                    body_snippet=body_snippet,
                )
            except httpx.TimeoutException:
                last_error = "Request timeout"
                if attempt >= self._config.retry_attempts:
                    return HttpProbeResult(
                        final_url=None,
                        status_code=None,
                        content_type=None,
                        content_length=None,
                        redirected=False,
                        redirect_count=0,
                        response_time_ms=None,
                        timeout=True,
                        error_text=last_error,
                    )
            except httpx.HTTPError as exc:
                last_error = str(exc)
                if attempt >= self._config.retry_attempts:
                    return HttpProbeResult(
                        final_url=None,
                        status_code=None,
                        content_type=None,
                        content_length=None,
                        redirected=False,
                        redirect_count=0,
                        response_time_ms=None,
                        network_error=True,
                        error_text=last_error,
                    )

            delay = self._config.retry_backoff_sec * attempt + random.uniform(0.0, self._config.retry_jitter_sec)
            time.sleep(delay)

        return HttpProbeResult(
            final_url=None,
            status_code=None,
            content_type=None,
            content_length=None,
            redirected=False,
            redirect_count=0,
            response_time_ms=None,
            network_error=True,
            error_text=last_error,
        )
