# Publishing MagicShelf and new creations

1. Keep the public API version unchanged for compatible releases; bump it for
   breaking module behavior. Bump the framework version in `magicshelf/__init__.py`
   and `tools/build_release.py`. Never replace assets from an existing release.
2. Target SteamOS and Steam Frame only. Run the unit tests,
   `tools/test_storefront.sh` and `tools/test_dashboard.sh`, and compile on each
   advertised architecture. Test the
   actual installer, VR library, on/off controls, a new module, and a failed update.
3. `bash build.sh` writes the verified framework archive, `catalog.json`,
   `install-magicshelf.py`, `Install.MagicShelf.desktop`, `framework.json`, and `SHA256SUMS` into `dist/`.
4. Create a framework release using the
   matching `vVERSION` tag and attach all the generated assets. A draft release
   keeps the download links unavailable until the complete set is ready.
5. Publish the release only after the checksum-pinned desktop launcher refers to
   that exact tag. The README links to the latest release's desktop launcher.
   The desktop launcher verifies the bootstrap, the bootstrap
   verifies the framework archive, and the framework verifies its file index.
6. Download the public desktop file and run it on a clean supported machine.
   Confirm no private paths, saves, account data, third-party game/model assets,
   signing keys, or developer settings entered the release.

Creations have independent repositories, versions, release tags and catalogs.
After the first complete public release, add the creation's stable latest
`catalog.json` URL to the framework's `collections.json` and run
`python3 tools/sync_catalog.py`. Commit both files. This is the one-time publisher
registration that makes a new creation appear in Discover for everyone;
installing an unpublished development package does not publish or register it.
The app fetches this live directory on collection checks, including when Discover
opens, and checks in the background every minute. Later releases stay in the
creation's own repository and need no framework release or registry edit.

The `Refresh creation collection` workflow mirrors published metadata into the
root catalog on registration and on a five-minute schedule for older app versions.
GitHub scheduling and CDN propagation can delay that compatibility mirror.
Current clients read each creation's own catalog directly. Uninstalling removes
the download and subscription, but leaves the collection followed and its listing
available to reinstall. Offline checks retain the last valid listings.

Start with `tools/new_creation.py` and follow [CREATING.md](CREATING.md). Pin an
exact SDK commit; SDK upgrades are explicit source changes. The Phone and Digivice
are working API 2 examples with their own backend lifecycle and configuration
commands. A simpler creation can continue using API 1.

Within a creation repository, update its manifest version, run its build/tests,
and package with `tools/package_creation.py` (or the creation's wrapper). Publish
the resulting `.magicshelf`, `catalog.json` and `SHA256SUMS` under a matching
`vX.Y.Z` tag. A creation's stable collection URL is
`https://github.com/OWNER/REPO/releases/latest/download/catalog.json`; each catalog
points to immutable, versioned package URLs and includes their SHA-256 and size.
Never overwrite published package assets. Followed collections show available
creations, and free subscriptions download/install future releases automatically.
On creations keep running while updates download; installation waits for Off,
unless the user explicitly chooses Update now. New permissions require review;
failed updates retain the working version. Run
`python3 tools/test_update_lifecycle.py --live` on the Frame to exercise cached
installation and failed-start recovery with an isolated disposable creation.
This uses real systemd services and readiness RPC but local package transfers.
Also complete the [tester readiness checks](TESTER_READINESS.md) on a fresh device.

Test a new creation release through its public catalog on the Frame. Confirm
that update, Off and removal affect only that creation, and that reinstall,
configuration and return-to-dock work. Game/model inputs and user data remain
local unless their distribution is explicitly supported by their licenses.

CI runs framework tests without a headset. A source build for a new architecture
must not be advertised as supported until its runtime and installer are tested.

The graphical desktop installer uses a checksum-pinned bootstrap and presents
progress, retry and Open MagicShelf controls without opening a terminal. Publish
all framework assets together before changing the public installer link. Future
framework update checks read the latest release's `framework.json`.

For creation releases, run the release workflow with the exact manifest version.
It builds first, verifies that version, creates a draft, uploads the full asset set,
and only then publishes it as latest. Keep distribution inputs pinned and record
their authors and permission separately from the source-code license.
