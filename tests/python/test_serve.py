from __future__ import annotations

import functools
import http.client
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from scripts.serve import QuietStaticHandler


def test_static_handler_serves_byte_ranges_for_audio():
    asset_root = Path(__file__).parent / "fixtures"
    asset = asset_root / "range-sample.mp3"

    handler = functools.partial(QuietStaticHandler, directory=str(asset_root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        connection = http.client.HTTPConnection(server.server_address[0], server.server_address[1], timeout=5)
        connection.request("GET", f"/{asset.name}", headers={"Range": "bytes=2-5"})
        response = connection.getresponse()
        body = response.read()
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert response.status == 206
    assert response.getheader("Accept-Ranges") == "bytes"
    assert response.getheader("Content-Range") == f"bytes 2-5/{asset.stat().st_size}"
    assert response.getheader("Content-Length") == "4"
    assert body == b"2345"
