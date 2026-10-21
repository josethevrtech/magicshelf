# Creating for MagicShelf

MagicShelf is the framework and storefront. A creation is a separate project
with its own repository, application code, assets, settings, issues, version
and release schedule. All creations and subscriptions are free. Supported
devices are Steam Frame and SteamOS development machines only.

## Repository boundaries

| Repository | Owns |
| --- | --- |
| `josethevrtech/magicshelf` | Native storefront, shelf/dock, SDK, module contracts, installation, subscriptions and rollback |
| `josethevrtech/magicshelf-android-phone` | Phone application, original geometry, Android controls and backend integration |
| `josethevrtech/magicshelf-digivice` | Digivice application, game integration, model import and device settings |

Creation repositories pin a MagicShelf SDK commit. Updating the main app does
not rebuild a creation. Updating a creation does not release the main app or
change another creation. A creation adopts a new SDK by changing its pin and
running its own checks. Shared grab/depth, shake recovery and dock fixes belong
in the SDK; creation-specific interactions belong in that creation's repository.

`sdk/version.json` identifies SDK **1.0.0**, module APIs **1 and 2**, and the existing
local-adapter compatibility API **2**. These are separate from the app version
and from each creation's version. Breaking runtime contracts require a new API
version; old hosts reject an unsupported API before installing it.

## Start a self-contained creation

Run the scaffold generator from a committed MagicShelf checkout:

```sh
python3 tools/new_creation.py /path/to/my-creation \
  --id org.example.my-creation --name 'My Creation' \
  --repository owner/my-creation
cd /path/to/my-creation
python3 tools/fetch_sdk.py
./build.sh
```

The starter uses a small clock face to demonstrate readiness, private data,
the host's assigned dock slot and clean shutdown. Replace its rendering and
interaction code with your creation. It is an independent source tree; there
is no need to add its application code to MagicShelf.

The generated `sdk.lock.json` pins a full framework commit. `fetch_sdk.py`
fetches only that revision. Builds can use `MAGICSHELF_SDK_DIR` for local SDK
development. `tools/build_sdk.py` also exports an SDK-only archive containing
headers, contracts, packaging tools and documentation.

For mesh-based creations, define `MAGICSHELF_CREATION_PROFILE` as the quoted
path to your own profile header, and put its directory on the include path.
The phone and Digivice repositories demonstrate this. The `compat` headers
retain the original prototype defaults for existing source compatibility;
new creations should supply their own identity and dimensions. The runtime
`MAGICSHELF_MODULE_KEY` always identifies the assigned shelf slot for packages.

## Build and publish independently

1. Keep a stable reverse-domain `module.json` ID and bump its own numeric
   `MAJOR.MINOR.PATCH` version. Never reuse a version for different bytes.
2. Build an aarch64 executable, staging only distributable files in a package
   directory. Keep saves in `MAGICSHELF_DATA_DIR`, outside the install directory.
3. Package it with the SDK:

   ```sh
   python3 vendor/magicshelf/tools/package_creation.py build/package \
     --repository owner/my-creation --output dist
   ```

4. Publish the `.magicshelf` archive, `catalog.json` and `SHA256SUMS` as assets
   of the creation repository's matching `vX.Y.Z` GitHub release. The generated
   workflow builds and checks the package before publishing a tag.
5. Register the stable catalog address with MagicShelf:
   `https://github.com/owner/my-creation/releases/latest/download/catalog.json`.
   The app can also list the creation in its curated catalog. The package URL
   always points to an immutable versioned release in the creation's repository.

Subscriptions check the registered catalog and update that creation alone.
The host preserves its On/Off state and data, rolls back failed readiness, and
requires review for added permissions. Ownership is pinned to the subscribed
catalog. Repository separation does not grant another catalog replacement rights.

Include screenshots, project links, artist credits and optional support links
in the manifest. See [MODULES.md](MODULES.md) for the complete wire protocol,
manifest, catalog, permissions, readiness and update contract. Include only
assets you may distribute; a source-code license does not relicense an artist's
model or another developer's game.

## Backends and module API 2

API 2 adds optional `control_entrypoint`, `cleanup_entrypoint` and
`startup_timeout_sec` (20–180 seconds). All are part of the manifest/catalog
identity checks. Control and cleanup paths must be executable files inside the
package. The host invokes control with `--show` or `--dock` and the private data
directory. Cleanup runs as systemd `ExecStopPost`, including after a crash; it
must be idempotent and affect only the creation's own external runtime.

`external-runtime` is an explicit permission to use installed Steam runtimes or
a creation-owned container. Such units allow the runtime's normal privilege
helpers (`NoNewPrivileges=no`); other creations retain `NoNewPrivileges=yes`.
This is a trust declaration, not a sandbox. Permission additions require review.
Module API 2 allows 32–4096 MiB per unit; API 1 retains its 1024 MiB limit.
The creation's complete process tree must fit its declared budget.

`MAGICSHELF_BACKEND_DATA_DIR` holds opaque external-runtime data (for example,
Android's user-namespace-owned filesystem). `MAGICSHELF_CACHE_DIR` holds
rebuildable runtime copies. These are outside the host's ordinary file snapshot:
rollback restores `MAGICSHELF_DATA_DIR`, never an Android image or external
runtime schema. A package must not silently migrate those external formats;
such migrations require their own recovery plan. Removal retains backend data.

All module API 1 packages remain supported. Old hosts reject API 2 packages.

The phone and Digivice now use API 2 packages with independent backend
lifecycles and private data directories. The phone requires Steam's Lepton;
the Digivice requires ARM64 Proton/Steam Linux Runtime plus separately supplied
game/model inputs. Those third-party files are not distributed by these source
repositories. The old local adapter API 2 is a different, legacy protocol kept
only for existing installations until they migrate.
