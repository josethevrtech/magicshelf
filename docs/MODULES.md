# MagicShelf module API v1

This is the compatibility boundary for independent toys. Additive optional fields
may be introduced within API v1. Changing field meaning, lifecycle behavior, or
required fields requires a new API version. The host must continue supporting v1
or explicitly reject it; it must not silently reinterpret an old module.

## Module archive

A `.magicshelf` file is a ZIP containing `module.json` at the root, an executable,
its assets and license. No install/uninstall shell hooks, links, absolute paths,
parent-directory paths, encrypted entries, duplicate paths or special files are
accepted. Limits are 100 MiB compressed, 400 MiB expanded, and 4,096 entries.
Files are extracted into staging and verified before becoming an installed version.

```json
{
  "schema_version": 1,
  "api_version": 1,
  "id": "org.example.my-toy",
  "version": "1.0.0",
  "name": "My toy",
  "description": "A short explanation of the toy.",
  "author": "Your name",
  "license": "MIT",
  "platform": "linux",
  "architecture": "aarch64",
  "entrypoint": "bin/my-toy",
  "permissions": ["vr-overlay"],
  "memory_mb": 128
}
```

IDs are lowercase dot/hyphen separated names, immutable across releases.
Versions are numeric `MAJOR.MINOR.PATCH`; releases must never replace bytes at an
existing version. A manifest describes one architecture (`aarch64` or `x86_64`).
One catalog can list the same ID for different architectures. Memory budgets
range from 32 to 1,024 MiB. API v1 permission names are `vr-overlay`, `network`,
and `user-files`; they describe capabilities for user review and are not an
enforced sandbox. Modules always run as the installing user, never as root.

## Catalog

```json
{"schema_version":1,"name":"My collection","modules":[
  {"...":"all manifest fields above", "url":"https://github.com/OWNER/REPO/releases/download/v1.0.0/my-toy.magicshelf",
   "sha256":"64 lowercase hexadecimal digits", "size_bytes":12345}
]}
```

Follow a catalog explicitly. Catalog and artifact URLs must use HTTPS GitHub
hosts; release redirects are checked. Each architecture variant appears once.
The downloaded manifest must agree with its catalog's ID, version, API,
architecture, executable, permissions and memory budget. The original collection
is retained so another followed collection cannot replace an installed toy.
Updates that request different permissions require a new installation review.
Catalogs and artifacts are not cryptographically signed in v1. The desktop
installer pins exact release hashes, and module hashes come from followed catalogs.

## Launch environment

The manager generates one systemd user service per packaged toy. It supplies:

| Variable | Contract |
| --- | --- |
| `MAGICSHELF_API_VERSION` | `1` |
| `MAGICSHELF_MODULE_ID` | The manifest's ID |
| `MAGICSHELF_MODULE_KEY` | OpenVR key `magicshelf.module.ID` |
| `MAGICSHELF_SESSION` | Private readiness nonce; do not log it |
| `MAGICSHELF_DATA_DIR` | Persistent writable module data; independent of version |
| `MAGICSHELF_RUNTIME_DIR` | Private runtime directory and manager socket |
| `MAGICSHELF_LAYOUT_DIR` | Shared shelf configuration directory |
| `MAGICSHELF_SHELF_OWNER` | `0`; a module must not create its own shelf |

Create overlays and load assets first, then send one newline-terminated message
to `MAGICSHELF_RUNTIME_DIR/manager.sock`:

```json
{"api_version":1,"method":"runtime.ready","params":{"id":"org.example.my-toy","token":"VALUE_OF_MAGICSHELF_SESSION"}}
```

Replies are one-line JSON containing `result` or `error`. The socket is accessible
only to the user. The desktop browser cannot call readiness or bundled-package
bootstrap. Readiness must succeed within 20 seconds when SteamVR is running.
When SteamVR is stopped, enable schedules the module for its next normal start.

On SIGTERM or OpenVR quit, stop the module cleanly, destroy persistent overlays,
and exit. The manager limits restart attempts and memory independently per toy.
Do not run transient raw-texture probes. Complete texture uploads before replacing
or destroying resources. Pocket Clock uses persistent file-backed overlays.

## Shelf placement and home

The host alone owns the shelf surface and ordering. `object-dock.json` in the
layout directory lists enabled OpenVR module keys from left to right. Reload
valid changes; retain the last valid configuration on parse errors. A removed
key has no shelf slot. At most 16 toys can be enabled.

The supplied `native/magicshelf_sdk.h` and placement helper adapt this layout to
OpenVR transforms and enforce launcher-only visibility. Pocket Clock demonstrates
their use. A new toy can render differently, but must use the shared slot pose
for its home position. It must not change the host's layout file or claim the
shared shelf lock. Keep user size/room pose separate from the temporary dock pose.
At home, fit the toy within `slot_spacing_m` minus a 1 cm margin and within
`object_height_m`. `magicshelfFit` calculates that temporary scale from model bounds
and follows the launcher's scene scale. This keeps future objects from covering
their neighbors while preserving their normal size outside the shelf.

`home.json` in the runtime directory contains `api_version:1` and an integer
`generation`. A changed generation requests Return home for all enabled toys.
Always-docked toys already satisfy the action. Picked-up toys should return to
their shared slot and clear any active grab. Legacy adapters use their existing
native Return to dock signal.

## Update and recovery

Installed versions live under `~/.local/share/magicshelf/modules/ID/versions/VERSION`.
State lives separately under `module-data/ID`. The manager stages the new archive,
stops an enabled toy, checkpoints its data, and switches the active version.
Failure to become ready restores the previous version and data. **Restore previous**
also checkpoints the current data before restoring the prior update's snapshot.
Removing a module keeps its data. Do not migrate another toy's data or shared
framework state. Rollback cannot undo arbitrary changes a trusted module makes
outside its data directory; design toys to write only inside their assigned data.

See [RELEASING.md](RELEASING.md) for the publishing checklist.

## Local device adapters

The existing phone and Digivice are adapters, not packaged modules. Their
capability marker `magicshelf-api-version` is independent of module API v1.
Adapter capability 2 adds `--hide`, which must release held input and hide the
object without stopping capture. `--dock` shows the same process in its shelf
slot. MagicShelf refuses hiding capability-1 adapters until their local shells
are upgraded. Packaged modules still stop when disabled.
