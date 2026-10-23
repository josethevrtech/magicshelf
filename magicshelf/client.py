"""Small stable API v1 client for tools and creation modules."""
import json
import os
import socket
from pathlib import Path
from .session import user_runtime

def runtime_dir():
    return user_runtime() / "magicshelf"

def request(method, params=None, timeout=235):
    packet = json.dumps({"api_version": 1, "method": method, "params": params or {}}).encode() + b"\n"
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(timeout)
        sock.connect(str(runtime_dir() / "manager.sock"))
        sock.sendall(packet)
        data = bytearray()
        while not data.endswith(b"\n"):
            part = sock.recv(65536)
            if not part:
                raise RuntimeError("MagicShelf disconnected")
            data.extend(part)
            if len(data) > 1024 * 1024:
                raise RuntimeError("MagicShelf response too large")
    result = json.loads(data)
    if "error" in result:
        raise RuntimeError(result["error"])
    return result["result"]

def ready():
    return request("runtime.ready", {"id": os.environ["MAGICSHELF_MODULE_ID"], "token": os.environ["MAGICSHELF_SESSION"]}, timeout=5)
