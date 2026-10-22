# MagicShelf module API v1

This is the compatibility boundary for independent creations. Additive optional fields
may be introduced within API v1. Changing field meaning, lifecycle behavior, or
required fields requires a new API version. The host must continue supporting v1
or explicitly reject it; it must not silently reinterpret an old module.

## Module archive

A `.magicshelf` file is a ZIP containing `module.json` at the root, an executable,
its assets and license. No install/uninstall shell hooks, links, absolute paths,
parent-directory paths, encrypted entries, duplicate paths or special files are
accepted. Limits are 1 GiB compressed, 2 GiB expanded, and 4,096 entries.
Files are extracted into staging and verified before becoming an installed version.

```json
{
  "schema_version": 1,
  "api_version": 1,
  "id": "org.example.my-creation",
  "version": "1.0.0",
  "name": "My creation",
  "description": "A short explanation of the creation.",
  "author": "Your name",
  "license": "MIT",
  "platform": "linux",
  "architecture": "aarch64",
  "entrypoint": "bin/my-creation",
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
  {"...":"all manifest fields above", "url":"https://github.com/OWNER/REPO/releases/download/v1.0.0/my-creation.magicshelf",
   "sha256":"64 lowercase hexadecimal digits", "size_bytes":12345}
]}
```

Follow a catalog explicitly. Catalog and artifact URLs must use HTTPS GitHub
hosts; release redirects are checked. Each architecture variant appears once.
The downloaded manifest must agree with its catalog's ID, version, API,
architecture, executable, permissions and memory budget. The original collection
is retained so another followed collection cannot replace an installed creation.
Updates that request different permissions require a new installation review.
Catalogs and artifacts are not cryptographically signed in v1. The desktop
installer pins exact release hashes, and module hashes come from followed catalogs.

## Storefront metadata and subscriptions

Optional presentation fields are additive within API v1. Include them in the
catalog and packaged manifest:

```json
{
  "price": 0,
  "category": "Utilities",
  "tagline": "A short invitation to try the creation.",
  "about": "A fuller description of what it does and how to use it.",
  "screenshots": [{"url": "https://raw.githubusercontent.com/OWNER/REPO/main/preview.png", "caption": "Creation in VR"}],
  "links": [{"label": "Source on GitHub", "url": "https://github.com/OWNER/REPO"}],
  "credits": [{"name": "Artist", "role": "3D model", "url": "https://example.org/artist", "support_url": "https://example.org/artist/support", "license": "The asset's actual license"}]
}
```

All creations are free; omit `price` or set it to zero. Category, tagline and
about have maximum lengths of 40, 120 and 2,000 characters. Up to six screenshots,
eight links and eight credits are supported. Screenshots are cached PNGs from
supported HTTPS GitHub hosts, at most 6 MiB, 4,096 pixels per dimension and
8 million pixels total. A missing preview does not block a download. Links and
artist/support URLs must be HTTPS. Supply genuine support links only; a profile
can stand alone when a donation page is unavailable. Artwork retains its own
license independently of the framework code.

`module.subscribe` takes `id`, boolean `subscribed`, and, when subscribing, the
reviewed `permissions` array. It installs an absent package Off and persists the
original catalog and approved permissions. The manager refreshes catalogs ten
seconds after startup and every five minutes. `subscriptions.sync` and
`catalog.refresh` request the same check in the background and return immediately.
`checking_updates` reports catalog activity; navigation remains available.
Catalogs are fetched independently, and unavailable sources retain their cached
listings without blocking healthy publishers. Failed checks retry after a minute;
failed creation downloads back off from one minute to fifteen minutes. A manual
check retries failed downloads immediately.

Downloaded archives are checked against size, SHA-256 and the package contract.
An update for an On creation is cached and reported as `ready`; its process keeps
running. Turning it Off installs the cached update automatically. Off creations
update immediately. **Update now** explicitly reviews and installs an update,
restarting that creation if it is On. New permissions always require review.
Unsubscribing cancels queued installation. A withdrawn update is discarded after
a successful catalog check.

Install and restore operations keep a recovery journal and a copy of module data.
A manager process interruption is recovered before another installation begins.
A failed first start after an update installed while Off restores the previous
version and its module data. **Restore previous** also holds the replaced version
so an automatic check does not reinstall it. A newer release can still update,
and explicit approval can retry the held version. Backups cover `module-data`;
creation-specific external runtimes and their data need their own recovery support.

The snapshot supplies `update_message`, `last_update_check`, `catalog_errors` and
per-creation `update_status` / `update_note`. Status values are `current`,
`available`, `ready`, `review`, `failed` and `held`. The transfer's `ready` stage
means the verified archive is waiting for Off, not that installation is complete.

Unsubscribing keeps the installed creation and saved data. Removing a download
cancels its subscription. A different catalog cannot replace a subscribed or
installed creation. Local device adapters have no downloadable package and cannot
be subscribed until a separate packaging/migration path is provided.

The snapshot supplies `subscribed`, `subscription_available`, `update_mode`
(`local`, `automatic`, or `manual`), and resolved screenshot URLs/paths for the
browser and native frontends. `module.link` accepts a creation ID and link index;
the manager resolves the URL from validated metadata rather than accepting an
arbitrary executable or URL from the native frontend.

## Launch environment

The manager generates one systemd user service per packaged creation. It supplies:

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
{"api_version":1,"method":"runtime.ready","params":{"id":"org.example.my-creation","token":"VALUE_OF_MAGICSHELF_SESSION"}}
```

Replies are one-line JSON containing `result` or `error`. The socket is accessible
only to the user. The desktop browser cannot call readiness or bundled-package
bootstrap. Readiness must succeed within 20 seconds when SteamVR is running.
When SteamVR is stopped, enable schedules the module for its next normal start.

On SIGTERM or OpenVR quit, stop the module cleanly, destroy persistent overlays,
and exit. The manager limits restart attempts and memory independently per creation.
Do not run transient raw-texture probes. Complete texture uploads before replacing
or destroying resources. The native dashboard uses a persistent EGL/GLES texture,
updates regions with `glTexSubImage2D`, finishes uploads before submission, and
releases the OpenVR overlay before destroying its GPU resources. Pocket Clock
still uses persistent file-backed overlays. The dashboard targets SteamOS and
Steam Frame only and follows Valve's [overlay texture contract](https://github.com/ValveSoftware/openvr/wiki/IVROverlay::SetOverlayTexture).

## Shelf placement and home

The host alone owns the shelf surface and ordering. `object-dock.json` in the
layout directory lists enabled OpenVR module keys from left to right. Reload
valid changes; retain the last valid configuration on parse errors. A removed
key has no shelf slot. At most 16 creations can be enabled.

The supplied `native/magicshelf_sdk.h` and placement helper adapt this layout to
OpenVR transforms and enforce launcher-only visibility. Pocket Clock demonstrates
their use. A new creation can render differently, but must use the shared slot pose
for its home position. It must not change the host's layout file or claim the
shared shelf lock. Keep user size/room pose separate from the temporary dock pose.
At home, fit the creation within `slot_spacing_m` minus a 1 cm margin and within
`object_height_m`. `magicshelfFit` calculates that temporary scale from model bounds
and follows the launcher's scene scale. This keeps future objects from covering
their neighbors while preserving their normal size outside the shelf.

`home.json` in the runtime directory contains `api_version:1` and an integer
`generation`. A changed generation requests Return home for all enabled creations.
Always-docked creations already satisfy the action. Picked-up creations should return to
their shared slot and clear any active grab. Legacy adapters use their existing
native Return to dock signal.

The shared dock helpers also support recovery: feed reset events through
`dockResetEvent`, consume `ObjectDock::takeHomeRequest()` after refresh, and clear
held input before returning home. The request is raised by spatial layout changes,
not by identical, invalid or appearance-only rewrites. `ObjectDock::canSnap`
tests whether a held phone/Digivice profile is near the visible dock; on release,
use the module's assigned slot, without changing ordering. Custom geometries
should use their own bounds for that proximity check. `ShakeToDock` accepts a
controller-tip position relative to the head and monotonic seconds; feed it only
during a grab and reset it when the grab ends. Always-docked modules need no
additional movement behavior.

## Update and recovery

Installed versions live under `~/.local/share/magicshelf/modules/ID/versions/VERSION`.
State lives separately under `module-data/ID`. The manager stages the new archive,
stops an enabled creation, checkpoints its data, and switches the active version.
Failure to become ready restores the previous version and data. **Restore previous**
also checkpoints the current data before restoring the prior update's snapshot.
Removing a module keeps its data. Do not migrate another creation's data or shared
framework state. Rollback cannot undo arbitrary changes a trusted module makes
outside its data directory; design creations to write only inside their assigned data.

See [RELEASING.md](RELEASING.md) for the publishing checklist.

## Local device adapters

The existing phone and Digivice are adapters, not packaged modules. Their
capability marker `magicshelf-api-version` is independent of module API v1.
Adapter capability 2 adds `--hide`, which must release held input and hide the
object without stopping capture. `--dock` shows the same process in its shelf
slot. MagicShelf refuses hiding capability-1 adapters until their local shells
are upgraded. Packaged modules still stop when disabled.

The manager also suspends the adapter's backend services with systemd's cgroup
v2 freezer. Android's exact Lepton container is paused separately using Podman,
because its processes live outside the wrapper service's cgroup. Off therefore
stops game/app execution and audio, while retaining memory and capture consumers
for resume. No system-wide audio controls or saved-game resets are involved.
On resumes the backend before showing the creation. Off disables independent
backend autostart links; On enables the shell, whose Wants dependencies start the
backends. Startup reconciliation reapplies the saved state without moving an
already enabled creation. Container commands must succeed; errors fail the toggle
and trigger restoration of its previous state.

## Module API 2

MagicShelf 0.3.2 supports API 1 and API 2. API 2 adds package-owned control and
cleanup entrypoints, explicit external-runtime permission, startup budgets and
separate opaque runtime data/cache directories. See [CREATING.md](CREATING.md)
for the lifecycle contract. Older hosts reject API 2 before installation.

## Guided setup, MagicShelf 0.3.8 and newer

A creation may declare `minimum_framework_version` as a semantic version and
`steam_requirements` as up to four objects with `appid`, a plain-language `title`,
and `files` relative to a Steam library's `steamapps/common` directory. The host
checks installed Steam manifests and required files without executing the creation.
Missing requirements show **Set up** in place of On. The setup page opens Steam's
normal installation flow and detects download progress and completion. Package
and catalog requirements must match exactly. The host passes each installed
requirement directory as `MAGICSHELF_STEAM_APP_APPID_DIR` to support other libraries.

`module.setup` accepts an installed creation `id` and one declared `appid`.
A caller cannot use this endpoint to open arbitrary apps or commands. Creations
own their requirements; MagicShelf does not hard-code Phone or Digivice setup.

User-initiated `module.subscribe` and `module.install` requests now acknowledge a
background job immediately. Poll the snapshot for transfer progress and completion;
returning from the request does not mean the installation has finished.

## MagicShelf updates

The official latest framework release supplies `framework.json` with a version
and per-architecture immutable URL, byte size and SHA-256. The host downloads and
verifies this archive in the background. **Update and reopen** runs installation
in a separate user service so restarting the manager does not interrupt it.
The installer verifies the new manager version and a frame rendered by the new
native process before accepting the update. Failure restores the previous release.
A journal lets an interrupted worker restore the original release; startup detects
an unfinished framework update after a device restart. Existing creation processes
are not restarted by a framework upgrade.
