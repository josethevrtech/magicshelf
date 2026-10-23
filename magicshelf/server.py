import hmac
import json
import os
import secrets
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .manager import Manager, atomic

def dispatch(manager, packet):
    if packet.get("api_version") not in (1, 2):
        raise ValueError("Unsupported MagicShelf API version")
    method, p = packet.get("method"), packet.get("params", {})
    if not isinstance(p, dict):
        raise ValueError("Invalid parameters")
    if method == "runtime.ready":
        key = p.get("id", "")
        expected = manager.sessions.get(key)
        if not expected or not isinstance(p.get("token"), str) or not hmac.compare_digest(expected, p["token"]):
            raise ValueError("Invalid module session")
        manager.ready.add(key)
        return {"accepted": True}
    if manager.framework.snapshot().get('stage') == 'installing' and method not in ('snapshot', 'modules.bootstrap'):
        raise ValueError('MagicShelf is updating. It will reopen in a moment.')
    def check_updates():
        result = manager.request_update_check()
        threading.Thread(target=manager.framework.check, daemon=True).start()
        return result
    actions = {
        "snapshot": lambda: manager.snapshot(),
        "modules.adopt": lambda: manager.adopt(),
        "modules.bootstrap": lambda: manager.bootstrap(),
        "framework.install": lambda: manager.framework.install(),
        "module.setup": lambda: manager.setup_step(p["id"], p.get("appid")),
        "module.setup.open": lambda: manager.setup_open(p["id"], p["appid"]),
        "module.open": lambda: manager.open(p["id"]),
        "module.toggle": lambda: manager.toggle(p["id"], p["enabled"]),
        "module.subscribe": lambda: manager.subscribe(p["id"], False) if p.get("subscribed") is False else manager.request_install(method, p),
        "module.link": lambda: manager.open_link(p["id"], p["index"]),
        "module.install": lambda: manager.request_install(method, p),
        "module.remove": lambda: manager.remove(p["id"]),
        "module.rollback": lambda: manager.rollback(p["id"]),
        "catalog.add": lambda: manager.add_catalog(p["url"]),
        "catalog.refresh": check_updates,
        "catalog.discover": manager.discover,
        "subscriptions.sync": check_updates,
        "home": lambda: manager.home_all(),
        "settings.update": lambda: manager.update_settings(p.get("changes")),
        "settings.reset": lambda: manager.reset_settings(p.get("group")),
        "app.link": lambda: manager.app_link(p.get("index")),
    }
    if method not in actions:
        raise ValueError("Unknown MagicShelf method")
    return actions[method]()

def response(manager, packet):
    try:
        return {"result": dispatch(manager, packet)}
    except Exception as e:
        manager.message = str(e)[:300]
        manager.publish()
        return {"error": str(e)[:500]}

class LocalServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True

def serve():
    manager = Manager()
    lock = (manager.runtime / "daemon.lock").open("a")
    import fcntl
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    address = manager.runtime / "manager.sock"
    address.unlink(missing_ok=True)

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.request.settimeout(240)
            try:
                line = self.rfile.readline(65537)
                if len(line) > 65536 or not line.endswith(b"\n"):
                    raise ValueError("Request is too large")
                result = response(manager, json.loads(line))
            except Exception as e:
                result = {"error": str(e)}
            self.wfile.write(json.dumps(result).encode() + b"\n")

    server = LocalServer(str(address), Handler)
    address.chmod(0o600)
    token = secrets.token_urlsafe(32)
    assets = Path(__file__).parent / "web"

    class Web(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, code, data, mime="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(data)

        def trusted(self):
            return self.headers.get("Host") == "127.0.0.1:" + str(http.server_port)

        def do_GET(self):
            if not self.trusted():
                return self.send(403, b'{}')
            if self.path == '/icon.png':
                try:
                    return self.send(200, (Path(__file__).resolve().parent.parent/'icon.png').read_bytes(), 'image/png')
                except OSError:
                    return self.send(404, b'{}')
            if self.path.startswith("/media/"):
                from .storefront import media_path
                try:
                    return self.send(200, media_path(self.path, manager.root).read_bytes(), "image/png")
                except (OSError, ValueError):
                    return self.send(404, b'{}')
            filename = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}.get(self.path)
            if not filename:
                return self.send(404, b'{}')
            mime = {"index.html": "text/html; charset=utf-8", "app.js": "text/javascript; charset=utf-8", "style.css": "text/css; charset=utf-8"}[filename]
            self.send(200, (assets / filename).read_bytes(), mime)

        def do_POST(self):
            if self.path != "/api" or not self.trusted() or self.headers.get("Origin") != "http://127.0.0.1:" + str(http.server_port):
                return self.send(403, b'{}')
            if not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
                return self.send(403, b'{}')
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 65536:
                    raise ValueError("Invalid request size")
                packet = json.loads(self.rfile.read(length))
                # Session readiness is for local module processes, not web pages.
                if packet.get("method") in ("runtime.ready", "modules.bootstrap"):
                    raise ValueError("Use the module socket")
                self.send(200, json.dumps(response(manager, packet)).encode())
            except (ValueError, KeyError) as e:
                self.send(400, json.dumps({"error": str(e)}).encode())

    http = ThreadingHTTPServer(("127.0.0.1", 0), Web)
    atomic(manager.runtime / "browser.json", {"url": "http://127.0.0.1:" + str(http.server_port) + "/#" + token})
    threading.Thread(target=http.serve_forever, daemon=True).start()
    def publish():
        while True:
            try:
                manager.setup.tick()
                manager.framework.automatic_install()
                manager.publish()
            except Exception as e:
                print("MagicShelf state:", e, flush=True)
            time.sleep(1)
    threading.Thread(target=publish, daemon=True).start()
    manager.framework.recover_after_restart()
    threading.Thread(target=manager.reconcile, daemon=True).start()
    def subscriptions():
        # No application scheduler or cron entry is needed: the installed manager
        # follows subscriptions for as long as the user's session is running.
        time.sleep(10)
        while True:
            try:
                if not manager.busy and manager.framework.snapshot().get('stage') != 'installing':
                    manager.sync_subscriptions()
                    manager.framework.check()
            except Exception as error:
                manager.update_message = "Automatic updates will retry: " + str(error)[:180]
            # Check promptly after a failed download or a temporary offline period.
            time.sleep(60)
    threading.Thread(target=subscriptions, daemon=True).start()
    try:
        server.serve_forever()
    finally:
        server.server_close()
        http.shutdown()
        address.unlink(missing_ok=True)
