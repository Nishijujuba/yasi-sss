#!/usr/bin/env python3
"""Build and serve the local static dist directory."""

from __future__ import annotations

import argparse
import functools
import http.server
import os
import socket
import subprocess
import webbrowser
from http import HTTPStatus
from pathlib import Path


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4173


class QuietStaticHandler(http.server.SimpleHTTPRequestHandler):
    """Suppress noisy tracebacks when browsers abort asset downloads."""

    _range_remaining: int | None = None

    @staticmethod
    def _parse_range_header(header: str, file_size: int) -> tuple[int, int] | None:
        unit, separator, range_spec = header.partition("=")
        if separator != "=" or unit.strip().lower() != "bytes" or "," in range_spec:
            return None

        start_text, dash, end_text = range_spec.strip().partition("-")
        if dash != "-":
            return None

        try:
            if start_text == "":
                suffix_length = int(end_text)
                if suffix_length <= 0:
                    return None
                start = max(file_size - suffix_length, 0)
                end = file_size - 1
            else:
                start = int(start_text)
                end = int(end_text) if end_text else file_size - 1
        except ValueError:
            return None

        if file_size <= 0 or start < 0 or start >= file_size or end < start:
            return None

        return start, min(end, file_size - 1)

    def end_headers(self) -> None:
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def send_head(self):  # type: ignore[no-untyped-def]
        self._range_remaining = None
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()

        range_header = self.headers.get("Range")
        if range_header is None:
            return super().send_head()

        try:
            file = open(path, "rb")
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return None

        file_size = os.fstat(file.fileno()).st_size
        parsed_range = self._parse_range_header(range_header, file_size)
        if parsed_range is None:
            file.close()
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header("Content-Range", f"bytes */{file_size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None

        start, end = parsed_range
        file.seek(start)
        self._range_remaining = end - start + 1
        self.send_response(HTTPStatus.PARTIAL_CONTENT)
        self.send_header("Content-type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.send_header("Content-Length", str(self._range_remaining))
        self.send_header("Last-Modified", self.date_time_string(os.fstat(file.fileno()).st_mtime))
        self.end_headers()
        return file

    def copyfile(self, source, outputfile):  # type: ignore[no-untyped-def]
        try:
            if self._range_remaining is not None:
                remaining = self._range_remaining
                while remaining > 0:
                    chunk = source.read(min(64 * 1024, remaining))
                    if not chunk:
                        break
                    outputfile.write(chunk)
                    remaining -= len(chunk)
                return
            super().copyfile(source, outputfile)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the frontend and serve the generated dist directory."
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Skip npm run build and serve the existing dist directory.",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the served URL in the default browser.",
    )
    parser.add_argument(
        "--no-open",
        action="store_false",
        dest="open",
        help="Do not open the served URL in a browser (default).",
    )
    parser.set_defaults(open=False)
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Host to bind (default: {DEFAULT_HOST}).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Preferred port to bind (default: {DEFAULT_PORT}).",
    )
    parser.add_argument(
        "--strict-port",
        action="store_true",
        help="Fail if --port is unavailable instead of trying later ports.",
    )
    return parser.parse_args()


def run_build(project_root: Path) -> None:
    print("Running npm run build...", flush=True)
    try:
        subprocess.run(["npm", "run", "build"], cwd=project_root, check=True)
    except FileNotFoundError:
        raise SystemExit(
            "Error: npm was not found. Install Node.js/npm or rerun with --no-build "
            "after creating dist."
        )
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Error: npm run build failed with exit code {exc.returncode}.")


def ensure_dist(dist_dir: Path) -> None:
    if not dist_dir.is_dir():
        raise SystemExit(
            f"Error: static directory does not exist: {dist_dir}\n"
            "Run npm run build first, or omit --no-build so this script can build it."
        )


def find_available_port(host: str, preferred_port: int, *, strict: bool = False) -> int:
    if preferred_port < 1 or preferred_port > 65535:
        raise SystemExit("Error: --port must be between 1 and 65535.")

    for port in range(preferred_port, 65536):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((host, port))
            except OSError:
                if strict:
                    raise SystemExit(f"Error: {host}:{preferred_port} is already in use.")
                continue
            return port

    raise SystemExit(f"Error: no available ports found from {preferred_port} to 65535.")


def serve(dist_dir: Path, host: str, preferred_port: int, should_open: bool, *, strict_port: bool) -> None:
    port = find_available_port(host, preferred_port, strict=strict_port)
    handler = functools.partial(
        QuietStaticHandler,
        directory=os.fspath(dist_dir),
    )
    server = http.server.ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{port}/"

    print(f"Serving {dist_dir} at {url}", flush=True)
    if should_open:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.", flush=True)
    finally:
        server.server_close()


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parent.parent
    dist_dir = project_root / "dist"

    if not args.no_build:
        run_build(project_root)
    ensure_dist(dist_dir)
    serve(dist_dir, args.host, args.port, args.open, strict_port=args.strict_port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
