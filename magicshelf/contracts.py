"""Public v1 contracts. Reject unsupported versions rather than guessing."""
import json
import platform
import re
from pathlib import PurePosixPath

ID = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+$")
VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
PERMISSIONS = {"vr-overlay", "network", "user-files"}
MAX_MODULES = 16

class ContractError(ValueError):
    pass

def require(condition, message):
    if not condition:
        raise ContractError(message)

def version(value):
    require(isinstance(value, str) and VERSION.fullmatch(value), "Version must be MAJOR.MINOR.PATCH")
    return tuple(map(int, value.split(".")))

def relative(value):
    require(isinstance(value, str) and value and "\\" not in value and "\x00" not in value, "Invalid package path")
    path = PurePosixPath(value)
    require(not path.is_absolute() and all(p not in (".", "..") for p in value.split("/")), "Package paths must stay inside the module")
    return value

def machine():
    return {"arm64": "aarch64", "amd64": "x86_64"}.get(platform.machine().lower(), platform.machine().lower())

def manifest(data):
    require(isinstance(data, dict), "Module manifest must be an object")
    require(data.get("schema_version") == 1 and type(data.get("schema_version")) is int, "Unsupported module schema")
    require(type(data.get("api_version")) is int and data["api_version"] == 1, "This module needs a different MagicShelf API")
    require(isinstance(data.get("id"), str) and ID.fullmatch(data["id"]), "Invalid module ID")
    version(data.get("version"))
    require(isinstance(data.get("name"), str) and 1 <= len(data["name"]) <= 80, "Invalid module name")
    require(isinstance(data.get("description"), str) and len(data["description"]) <= 500, "Invalid description")
    require(isinstance(data.get("author"), str) and 1 <= len(data["author"]) <= 100, "An author is required")
    require(isinstance(data.get("license"), str) and data["license"], "A module license is required")
    require(data.get("platform") == "linux", "Only Linux modules are supported")
    require(data.get("architecture") in ("aarch64", "x86_64"), "Unsupported module architecture")
    relative(data.get("entrypoint"))
    require(isinstance(data.get("permissions"), list) and all(p in PERMISSIONS for p in data["permissions"]), "Unknown module permission")
    require(len(set(data["permissions"])) == len(data["permissions"]), "Duplicate permission")
    require("vr-overlay" in data["permissions"], "A toy must declare vr-overlay")
    require(type(data.get("memory_mb", 256)) is int and 32 <= data.get("memory_mb", 256) <= 1024, "Invalid memory budget")
    return data

def catalog(data):
    require(isinstance(data, dict) and data.get("schema_version") == 1, "Unsupported catalog schema")
    require(isinstance(data.get("name"), str) and len(data["name"]) <= 100, "Invalid catalog name")
    require(isinstance(data.get("modules"), list) and len(data["modules"]) <= 200, "Invalid catalog modules")
    seen = set()
    for item in data["modules"]:
        manifest(item)
        identity = (item["id"], item["architecture"])
        require(identity not in seen, "Duplicate catalog module architecture")
        seen.add(identity)
        require(isinstance(item.get("sha256"), str) and re.fullmatch(r"[a-f0-9]{64}", item["sha256"]), "Missing SHA-256")
        require(isinstance(item.get("size_bytes"), int) and 0 < item["size_bytes"] <= 100 * 1024 * 1024, "Invalid download size")
        require(isinstance(item.get("url"), str), "Missing package URL")
    return data

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))
