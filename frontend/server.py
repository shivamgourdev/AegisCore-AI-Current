from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import os

ROOT = Path(__file__).resolve().parent
BACKEND = "http://127.0.0.1:8000"

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        print("[sandbox]", fmt % args)

    def _proxy(self):
        path = self.path
        if path.startswith("/api/"):
            target = BACKEND + path[4:]  # strip /api/ prefix
        elif path == "/ask":
            target = BACKEND + "/ask"
        else:
            self.send_error(404, "Unknown API route")
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else None
        headers = {}
        for key in ("Content-Type", "Accept"):
            if self.headers.get(key):
                headers[key] = self.headers[key]
        request = Request(target, data=body, headers=headers, method=self.command)
        try:
            with urlopen(request, timeout=120) as response:
                content = response.read()
                status = response.status
                content_type = response.headers.get("Content-Type", "application/json")
        except HTTPError as exc:
            content = exc.read()
            status = exc.code
            content_type = exc.headers.get("Content-Type", "application/json")
        except (URLError, TimeoutError, OSError) as exc:
            content = ('{"detail":"Cannot reach backend at ' + BACKEND +
                       '. Start the FastAPI backend first. Details: ' +
                       str(exc).replace('"', "'") + '"}').encode("utf-8")
            status = 502
            content_type = "application/json"
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self._proxy()
        if self.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        return self._proxy()

    def do_PUT(self):
        return self._proxy()

    def do_DELETE(self):
        return self._proxy()

if __name__ == "__main__":
    os.chdir(ROOT)
    print("AegisCore AI Sandbox: http://127.0.0.1:5500")
    print("Backend proxy target: " + BACKEND)
    print("Keep this terminal open while using the sandbox.")
    ThreadingHTTPServer(("127.0.0.1", 5500), Handler).serve_forever()
