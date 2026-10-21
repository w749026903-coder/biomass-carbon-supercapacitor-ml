"""Read-only localhost preview for a single authorized run; never serve the repository."""
from pathlib import Path
import argparse
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        super().end_headers()

    def do_GET(self):
        if self.path == '/':
            self.send_response(302)
            self.send_header('Location', '/dashboard/dist/index.html')
            self.end_headers()
            return
        super().do_GET()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-dir', type=Path, required=True)
    p.add_argument('--port', type=int, default=8765)
    args = p.parse_args()
    folder = args.run_dir.resolve()
    if ROOT not in folder.parents or not (folder / 'training_plan.json').is_file():
        raise ValueError('A single run directory within the project is required.')
    handler = functools.partial(Handler, directory=str(folder))
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler)
    print(f'Local training progress: http://127.0.0.1:{args.port}/', flush=True)
    server.serve_forever()
