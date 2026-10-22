"""Run native acceptance with a generated loopback-only HTTP fixture server."""
import argparse
import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class FixtureHandler(BaseHTTPRequestHandler):
    requests_seen = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        self.requests_seen.append(('GET', path))
        if path == '/redirect':
            self.send_response(302)
            self.send_header('Location', '/payload')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        data = {'/payload': b'loopback office', '/binary': bytes(range(256)),
                '/large': bytes(i % 251 for i in range(600000)), '/empty': b''}.get(path)
        self.send_response(200 if data is not None else 404)
        data = data if data is not None else b'fixture missing'
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        try:
            self.wfile.write(data)
        except (ConnectionResetError, BrokenPipeError):
            pass

    def do_POST(self):
        self.requests_seen.append(('POST', self.path))
        self.send_response(501)
        self.send_header('Content-Length', '0')
        self.end_headers()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    args = parser.parse_args()
    work = args.work_dir.resolve()
    root = work / 'transport-fixtures'
    root.mkdir(exist_ok=True)
    if any(root.iterdir()):
        raise ValueError('Prior transport test evidence remains; inspect before retrying')
    result_path = work / 'transport-test-result.json'
    if result_path.exists():
        result_path.unlink()
    server = ThreadingHTTPServer(('127.0.0.1', 0), FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = subprocess.run([str(args.exe), str(root), str(result_path),
                                 'http://127.0.0.1:' + str(server.server_port)],
                                cwd=work / 'bin', timeout=180)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    (work / 'transport-http-evidence.json').write_text(json.dumps({
        'bind_address': '127.0.0.1', 'requests': FixtureHandler.requests_seen,
        'external_requests_from_fixture_server': False}), 'utf-8')
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
