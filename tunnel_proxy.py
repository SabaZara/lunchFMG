"""Tiny localhost header-injecting reverse proxy (stdlib only).

WHY THIS EXISTS
---------------
A Cloudflare *quick* tunnel (trycloudflare.com, no account) cannot inject an
arbitrary custom request header to the origin on its own. To make the
remote-only gate airtight with a shared secret, we put this 30-line proxy
between cloudflared and the app:

    browser --HTTPS--> Cloudflare --> cloudflared(local) --> THIS PROXY --> app

THIS PROXY:
  * listens on 127.0.0.1:<PROXY_PORT> (NOT on the LAN),
  * adds  X-Tunnel-Secret: <TUNNEL_SECRET>  to every forwarded request,
  * forwards everything to the app on 127.0.0.1:<APP_PORT>.

cloudflared points at the proxy port; the app (gated) sees the secret only on
tunneled traffic. The kiosk PC's own browser hits the APP port directly, which
has no secret, so /admin etc. stay blocked locally. Both ports are 127.0.0.1
only, so the cafeteria LAN can reach neither.

Run:  python tunnel_proxy.py            (reads env: PROXY_PORT, PORT, TUNNEL_SECRET, HOST)
"""
from __future__ import annotations

import http.client
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.config import get_settings

_settings = get_settings()
APP_HOST = "127.0.0.1"
APP_PORT = _settings.port
PROXY_PORT = int(os.environ.get("PROXY_PORT", str(APP_PORT + 1)))
TUNNEL_SECRET = _settings.tunnel_secret

# Hop-by-hop headers must not be forwarded verbatim.
_HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
}


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):  # silence access log
        pass

    def _proxy(self, method: str) -> None:
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else None

        out_headers = {}
        for k, v in self.headers.items():
            if k.lower() in _HOP_BY_HOP:
                continue
            out_headers[k] = v
        # Inject the shared secret proving "this came through the tunnel".
        out_headers["X-Tunnel-Secret"] = TUNNEL_SECRET
        # Tell the app it's effectively HTTPS (so cookies are marked Secure).
        out_headers.setdefault("X-Forwarded-Proto", "https")

        try:
            conn = http.client.HTTPConnection(APP_HOST, APP_PORT, timeout=30)
            conn.request(method, self.path, body=body, headers=out_headers)
            resp = conn.getresponse()
            data = resp.read()
        except Exception as exc:  # noqa: BLE001
            self.send_error(502, f"upstream error: {exc}")
            return

        self.send_response(resp.status)
        for k, v in resp.getheaders():
            if k.lower() in _HOP_BY_HOP:
                continue
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if data:
            self.wfile.write(data)
        conn.close()

    def do_GET(self):     self._proxy("GET")      # noqa: E704
    def do_POST(self):    self._proxy("POST")     # noqa: E704
    def do_PUT(self):     self._proxy("PUT")      # noqa: E704
    def do_DELETE(self):  self._proxy("DELETE")   # noqa: E704
    def do_PATCH(self):   self._proxy("PATCH")    # noqa: E704
    def do_HEAD(self):    self._proxy("HEAD")     # noqa: E704


def main() -> None:
    if not TUNNEL_SECRET:
        print("[tunnel_proxy] TUNNEL_SECRET is empty; refusing to start.", file=sys.stderr)
        sys.exit(1)
    server = ThreadingHTTPServer((APP_HOST, PROXY_PORT), ProxyHandler)
    print(f"[tunnel_proxy] 127.0.0.1:{PROXY_PORT} -> app 127.0.0.1:{APP_PORT} (+secret header)")
    server.serve_forever()


if __name__ == "__main__":
    main()
