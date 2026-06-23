"""Remote-only gate.

The kiosk PC must only ever see the scan screen. Admin / reports / login and
their APIs are reachable ONLY through the remote tunnel/proxy, which injects a
shared secret header on every tunneled request. This middleware:

  * ALWAYS allows the scan page ("/") and the scan API ("/api/scan"), plus
    static assets and health — so the kiosk works fully offline.
  * For every PROTECTED path, requires the exact TUNNEL_SECRET header.

If TUNNEL_SECRET is unset we fail CLOSED (block all protected paths), so a
misconfigured deploy never accidentally exposes admin on the LAN.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .config import get_settings

TUNNEL_HEADER = "x-tunnel-secret"

# Paths the kiosk needs offline. Everything NOT matched here that touches
# admin/reports/login is protected.
_ALWAYS_OPEN_EXACT = {"/", "/healthz", "/favicon.ico"}
_ALWAYS_OPEN_PREFIXES = ("/static/", "/api/scan")

# Protected surfaces (pages + APIs).
_PROTECTED_PREFIXES = (
    "/admin",
    "/reports",
    "/login",
    "/api/people",
    "/api/reports",
    "/api/login",
    "/api/logout",
    "/api/me",
)


def _is_always_open(path: str) -> bool:
    if path in _ALWAYS_OPEN_EXACT:
        return True
    return any(path == p or path.startswith(p) for p in _ALWAYS_OPEN_PREFIXES)


def _is_protected(path: str) -> bool:
    return any(path == p or path.startswith(p) for p in _PROTECTED_PREFIXES)


class TunnelGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        path = request.url.path
        settings = get_settings()

        if _is_always_open(path):
            return await call_next(request)

        if _is_protected(path):
            secret = settings.tunnel_secret
            provided = request.headers.get(TUNNEL_HEADER)
            # Fail closed if no secret configured, or mismatch.
            if not secret or provided != secret:
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "ეს გვერდი ხელმისაწვდომია მხოლოდ დისტანციურად (ტუნელით)."
                    },
                )

        return await call_next(request)
