import argparse
import json
import subprocess
import sys
from pathlib import Path
from .client import request, runtime_dir
from .session import service_environment

def main():
    p = argparse.ArgumentParser(prog="magicshelf")
    p.add_argument("command", choices=["serve", "open", "web", "list", "adopt", "enable", "disable", "install", "remove", "rollback", "follow", "refresh", "home"])
    p.add_argument("value", nargs="?")
    p.add_argument("--permissions", nargs="*", default=[])
    args = p.parse_args()
    if args.command == "serve":
        from .server import serve
        return serve()
    if args.command == "open":
        launcher = Path(__file__).resolve().parent.parent / "bin/magicshelf-vr-launch"
        return subprocess.run([str(launcher)], check=True).returncode
    if args.command == "web":  # Explicit developer diagnostics, never the app launcher.
        subprocess.run(["systemctl", "--user", "start", "magicshelf.service"], env=service_environment(), check=True)
        import time
        for _ in range(40):
            try:
                url = json.loads((runtime_dir() / "browser.json").read_text())["url"]
                return subprocess.run(["xdg-open", url], check=True).returncode
            except FileNotFoundError:
                time.sleep(.1)
        raise RuntimeError("MagicShelf did not start")
    methods = {"list": "snapshot", "adopt": "modules.adopt", "enable": "module.toggle", "disable": "module.toggle", "install": "module.install", "remove": "module.remove", "rollback": "module.rollback", "follow": "catalog.add", "refresh": "catalog.refresh", "home": "home"}
    params = {"id": args.value, "enabled": args.command == "enable", "url": args.value, "permissions": args.permissions}
    print(json.dumps(request(methods[args.command], params), indent=2))

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("MagicShelf:", e, file=sys.stderr)
        sys.exit(1)
