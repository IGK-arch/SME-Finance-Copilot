"""Only public sandbox operations. No private-world import or filesystem reads."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from finance.domain import FinanceError, Json, require


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


class SandboxAdapter:
    def __init__(self, base_url: str, execute_token: str) -> None:
        parsed = urlparse(base_url)
        require(
            parsed.scheme == "http"
            and parsed.hostname == "127.0.0.1"
            and parsed.path in ("", "/")
            and not parsed.username
            and not parsed.query,
            "POLICY_DENIED",
            "Only the loopback sandbox is allowed",
        )
        self.base_url = base_url.rstrip("/")
        self._token = execute_token
        self._opener = build_opener(NoRedirect)

    def _request(self, path: str, value: Json | None = None) -> Json:
        request = Request(
            self.base_url + path,
            data=json.dumps(value).encode() if value is not None else None,
            headers={"Authorization": "Bearer " + self._token, "Content-Type": "application/json"},
        )
        try:
            with self._opener.open(request, timeout=5) as response:
                return json.loads(response.read(1_000_000))
        except HTTPError as exc:
            if exc.code >= 500:
                raise FinanceError(
                    "TEMPORARY_UNAVAILABLE", "Sandbox outcome is unknown", True
                ) from exc
            raise FinanceError("SANDBOX_REJECTED", "Sandbox rejected the request") from exc
        except (URLError, TimeoutError) as exc:
            raise FinanceError(
                "TEMPORARY_UNAVAILABLE", "Sandbox unavailable; outcome is unknown", True
            ) from exc

    def observation(self) -> Json:
        return self._request("/observation")

    def status(self, key: str) -> Json:
        return self._request("/status", {"stable_key": key})

    def submit(self, command: Json, fault: str = "none") -> Json:
        return self._request("/commands", {"command": command, "fault": fault})


class UnsupportedBankAdapter:
    def submit(self, command: Json) -> Json:
        raise FinanceError("UNSUPPORTED_BACKEND", "No production banking integration implemented")
