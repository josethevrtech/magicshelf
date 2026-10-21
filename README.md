# MagicShelf

A shelf where you get to play around with silly ideas I made.

A floating shelf and launcher for downloadable SteamVR toys. Install MagicShelf
once, follow a collection, then choose which toys belong on your shelf.

## Install

In Desktop Mode, download [Install MagicShelf.desktop](https://github.com/josethevrtech/magicshelf/releases/download/v0.1.2/Install%20MagicShelf.desktop)
to your desktop and double-click it. If your desktop asks whether to execute or
trust the downloaded launcher, allow it. Open the new **MagicShelf** shortcut or
select **MagicShelf** in SteamVR's dashboard.

The installer runs under your user account and needs no administrator password.
It verifies the release before installing into `~/.local/share/magicshelf`.
It does not modify the operating system or restart SteamVR.

The first binary release targets **Steam Frame / Linux aarch64**, with Python
3.12+, systemd user services, Cairo/json-c, and SteamVR installed at
`/opt/steamvr`. x86_64 is a source build target, not a tested downloadable release.
This is an early framework release; the installation and migration validation
is recorded in [docs/VALIDATION.md](docs/VALIDATION.md).

## Your collection

- Turn a toy on to give it a shelf slot; turn it off to stop its module process.
- Follow GitHub catalogs and review each toy before installing it.
- Install and update toys independently. Failed readiness checks restore the
  previous code and module data; **Restore previous** also supports manual recovery.
- Remove a toy while keeping its saved data.
- **Return toys home** returns the active toys to the shelf.

**Pocket Clock** is an optional developer example, excluded from the default shelf.
MagicShelf is the single dashboard entry; use **Open** in its library for either device.
The existing Android phone and Digivice can be adopted on a migrated installation.
Their switches control their visual shells; their existing app backends keep
running to preserve the Android session and pet. MagicShelf does not distribute
the Android image, the Digital Partner game, or third-party Digivice artwork.

The shelf appears beside Steam's launcher and hides while the launcher is closed
or another dashboard app is active. Native expanded sidebar labels cover the
shelf. Modules can implement their own pick-up and room behavior.

## A stable module contract

API v1 defines the manifest, package format, environment, readiness message,
shelf configuration, and home action. Unsupported API or schema versions are
rejected before execution. Modules run in separate, memory-limited user services.
See [the module contract](docs/MODULES.md) and the [Pocket Clock source](examples/pocket-clock).

Permissions are declarations for review, not a complete security sandbox. Native
toys run as your user and can access user resources. Only install modules from
publishers you trust. Checksum verification detects changed downloads; it does
not protect against a compromised publisher or catalog.

## Develop

```sh
python3 -m unittest discover -s tests -v
bash build.sh
```

Build requirements: C++17, pkg-config, Cairo, json-c, EGL/GLES development files,
and the matching SteamVR `libopenvr_api.so`. The vendored OpenVR header is under
Valve's BSD license; see [OPENVR-LICENSE.txt](OPENVR-LICENSE.txt).

Release artifacts are written to `dist/`. Build on the target architecture.
The build also creates a catalog, a `.magicshelf` module archive, a verified
bootstrap installer, and the downloadable `.desktop` launcher.

## Remove MagicShelf

```sh
python3 ~/.local/share/magicshelf/current/uninstall.py
```

This stops MagicShelf integration and downloaded modules and keeps releases and saved
data. Migrated phone/Digivice shells return to their standalone shelf behavior.
Existing game and Android installations remain in their original locations.

MagicShelf code and Pocket Clock: MIT. OpenVR: Valve BSD 3-Clause. No affiliation
with Valve, Steam, or Decky Loader. The desktop download flow follows the familiar
[Decky installer pattern](https://github.com/SteamDeckHomebrew/decky-installer).
