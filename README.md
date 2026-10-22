# MagicShelf

MagicShelf is a home for my VR creations. Subscribe to your favorites and make your shelf your own.

Built for **SteamOS and Steam Frame only**. Browse the native SteamVR collection, open a creation for
screenshots and settings, and find its project links and artist credits.
Subscriptions download published creations and keep them up to date.

## See MagicShelf

A look at the **0.3.6 development build** on Steam Frame. The public installer below is still **0.1.3**.

[![Watch the MagicShelf feature tour](https://github.com/user-attachments/assets/a3043c97-b729-4f46-8c98-a9f49aa84bb7)](https://github.com/user-attachments/assets/b95519ce-6af4-4641-800a-8c65aad8a6dd)

**[Watch the 48-second feature tour with music](https://github.com/user-attachments/assets/b95519ce-6af4-4641-800a-8c65aad8a6dd)** — explore creations, card On/Off controls, artist credits, permission reviews, automatic downloads and shelf customization.

| Discover | Creation details |
| --- | --- |
| ![Discover on Steam Frame](https://github.com/user-attachments/assets/b4ccd554-1e5b-45ff-ba4d-64f458f648a0) | ![Android Phone (Virtual)](https://github.com/user-attachments/assets/33bc835e-c0ba-4341-9958-5cf267bd5446) |
| **Artist credits** | **Shelf settings** |
| ![Smartphone Digivice artist credits](https://github.com/user-attachments/assets/e0a8cbb0-e3cc-43d0-b6bf-f9601ec10187) | ![Shelf customization controls](https://github.com/user-attachments/assets/94353032-21fa-4667-8835-db186a7d807f) |

The tour uses the native app renderer with current creation metadata. Install and download scenes are illustrative. Music: **Shelf Lights**, composed and synthesized for this tour without external samples. Digivice model: [Jojogape](https://x.com/jojogape); Digital Partner game: [Aludeku](https://aludeku.itch.io/digital-partner-digimon).

## Install

In Desktop Mode, download [Install.MagicShelf.desktop](https://github.com/josethevrtech/magicshelf/releases/download/v0.1.3/Install.MagicShelf.desktop)
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

## Published installer (0.1.3)

- Turn a creation on to give it a shelf slot; turn it off to stop its module process.
- Follow GitHub catalogs and review each creation before installing it.
- Install and update creations independently. Failed readiness checks restore the
  previous code and module data; **Restore previous** also supports manual recovery.
- Remove a creation while keeping its saved data.

**Pocket Clock** is an optional developer example, excluded from the default shelf.
MagicShelf is the single dashboard entry; use **Open** in its library for either device.
The existing Android phone and Digivice can be adopted on a migrated installation.
Their switches hide/show the devices while keeping the shells and capture
connections alive to preserve the Android session and pet. Local adapter
capability v2 is required for this behavior. MagicShelf does not distribute
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
creations run as your user and can access user resources. Only install modules from
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
