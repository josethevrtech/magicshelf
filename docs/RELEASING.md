# Publishing MagicShelf and new toys

1. Keep the public API version unchanged for compatible releases; bump it for
   breaking module behavior. Bump the framework version in `magicshelf/__init__.py`
   and `tools/build_release.py`. Never replace assets from an existing release.
2. Run the unit tests and compile on each advertised architecture. Test the
   actual installer, VR library, on/off controls, a new module, and a failed update.
3. `bash build.sh` writes verified framework and module archives, `catalog.json`,
   `install-magicshelf.py`, `Install MagicShelf.desktop`, and `SHA256SUMS` into `dist/`.
4. Commit the generated catalog to the repository. Create a release using the
   matching `vVERSION` tag and attach all the generated assets. A draft release
   keeps the download links unavailable until the complete set is ready.
5. Publish the release only after the checksum-pinned desktop launcher refers to
   that exact tag. The desktop launcher verifies the bootstrap, the bootstrap
   verifies the framework archive, and the framework verifies its file index.
6. Download the public desktop file and run it on a clean supported machine.
   Confirm no private paths, saves, account data, third-party game/model assets,
   signing keys, or developer settings entered the release.

To publish a new toy, copy the Pocket Clock manifest/package layout, choose a
unique permanent ID, implement API v1 readiness and shelf/home behavior, and
publish its archive as a GitHub release asset. Add its complete manifest, URL,
SHA-256 and byte length to the collection catalog. Users receive the catalog
change when they choose Check for updates; installation remains their choice.

CI runs framework tests without a headset. A source build for a new architecture
must not be advertised as supported until its runtime and installer are tested.
