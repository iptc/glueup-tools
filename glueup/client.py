"""Glue Up open API v2 client.

Auth model (from the Apiary docs and the PHP examples Glue Up sent us):

    digest = hmac_sha256(method + publicKey + version + ts, privateKey).hex()
    header `a` = "v=1.0;k=<publicKey>;ts=<ts>;d=<digest>"
    header `token` (optional) = session token from POST user/session
    header `tenantId` = top-level account ID
    header `requestOrganizationId` = sub-org context

The timestamp must be fresh — Glue Up rejects headers older than ~20 minutes
with error code -1005, so we generate a new signature for each request rather
than caching.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from typing import Any

import requests


class GlueUpError(Exception):
    """Raised when Glue Up returns a non-2xx response or an `errors` payload."""

    def __init__(self, message: str, *, http_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.http_code = http_code
        self.payload = payload


@dataclass
class GlueUpConfig:
    public_key: str
    private_key: str
    tenant_id: str
    org_id: str
    base_url: str = "https://api-services.glueup.com/v2/"
    version: str = "1.0"

    @classmethod
    def from_env(cls) -> "GlueUpConfig":
        try:
            return cls(
                public_key=os.environ["GLUEUP_PUBLIC_KEY"],
                private_key=os.environ["GLUEUP_PRIVATE_KEY"],
                tenant_id=os.environ["GLUEUP_TENANT_ID"],
                org_id=os.environ["GLUEUP_ORG_ID"],
                base_url=os.environ.get("GLUEUP_BASE_URL", cls.base_url),
            )
        except KeyError as missing:
            raise GlueUpError(f"Missing required env var: {missing.args[0]}") from None


class GlueUpClient:
    """Thin wrapper over Glue Up's HTTP API.

    Endpoint paths are passed without the base URL — e.g.
    `client.get("membershipDirectory/settings")`.
    """

    def __init__(self, config: GlueUpConfig | None = None, *, session_token: str | None = None):
        self.config = config or GlueUpConfig.from_env()
        self.session_token = session_token
        self._http = requests.Session()

    # ------------------------------------------------------------------ auth

    def _digest(self, method: str, ts_ms: int) -> str:
        base = f"{method.upper()}{self.config.public_key}{self.config.version}{ts_ms}"
        return hmac.new(
            self.config.private_key.encode("utf-8"),
            base.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _auth_headers(self, method: str) -> dict[str, str]:
        ts_ms = int(time.time() * 1000)
        d = self._digest(method, ts_ms)
        headers = {
            "a": f"v={self.config.version};k={self.config.public_key};ts={ts_ms};d={d}",
            "tenantId": str(self.config.tenant_id),
            "requestOrganizationId": str(self.config.org_id),
            "Accept": "application/json",
            "Cache-Control": "no-cache",
        }
        if self.session_token:
            headers["token"] = self.session_token
        return headers

    # ------------------------------------------------------------------ http

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> dict:
        url = self.config.base_url + path.lstrip("/")
        headers = self._auth_headers(method)
        if json is not None:
            headers["Content-Type"] = "application/json;charset=UTF-8"

        resp = self._http.request(method, url, headers=headers, json=json, params=params, timeout=30)

        try:
            body = resp.json()
        except ValueError:
            raise GlueUpError(
                f"Non-JSON response from {method} {path}: {resp.text[:200]}",
                http_code=resp.status_code,
            )

        # The Apiary docs describe an envelope `{"code": ..., "data": {"value", "errors", "warnings", "metadata"}}`
        # but the live API actually returns `{"value", "errors", "warnings", "metadata"}` flat — no `data` wrapper,
        # no `code` field (HTTP status is the source of truth). Tolerate both shapes.
        payload = body.get("data", body) if isinstance(body, dict) else {}
        errors = payload.get("errors") or [] if isinstance(payload, dict) else []
        if resp.status_code >= 400 or errors:
            raise GlueUpError(
                f"{method} {path} failed: HTTP {resp.status_code}, errors={errors}",
                http_code=resp.status_code,
                payload=body,
            )
        return body

    def get(self, path: str, **kwargs) -> dict:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, json: Any = None, **kwargs) -> dict:
        return self.request("POST", path, json=json, **kwargs)

    def put(self, path: str, json: Any = None, **kwargs) -> dict:
        return self.request("PUT", path, json=json, **kwargs)

    def delete(self, path: str, **kwargs) -> dict:
        return self.request("DELETE", path, **kwargs)
