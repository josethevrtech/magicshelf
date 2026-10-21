# MagicShelf

MagicShelf is a home for my VR creations. Subscribe to your favorites and make your shelf your own.

Built for **SteamOS and Steam Frame only**. Browse the native SteamVR collection, open a creation for
screenshots and settings, and find its project links and artist credits.
Subscriptions download published creations and keep them up to date.

## Framework and creations

Each creation has its own source repository and release cycle:
[Android Phone](https://github.com/josethevrtech/magicshelf-android-phone) and
[Digivice](https://github.com/josethevrtech/magicshelf-digivice).
MagicShelf owns the storefront, shelf, SDK, installation and updates.
Creation projects pin the SDK and can develop independently.
See [Creating for MagicShelf](docs/CREATING.md) to start a new creation.
The independent packages target module API 2; legacy installations retain their compatibility adapters until migrated.

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
`/opt/steamvr`. x86_64 is a SteamOS development target, not a tested downloadable release.
This is an early framework release; the installation and migration validation
is recorded in [docs/VALIDATION.md](docs/VALIDATION.md).

## Your collection

The storefront is installed locally as **0.3.2** for testing. The public installer
above remains **0.1.3** until a new release is published. The VR storefront opens
at 1.8 m wide and renders at 2560 × 1800 for sharper text. The desktop shortcut
opens this same native dashboard. The display stays on one GPU texture while
browsing; controller hover/press feedback updates only the affected region.
Release the trigger over a control to activate it, or move away to cancel.
Navigation remains available while downloads and updates run.

- **Discover** shows screenshot cards; **My Shelf** shows your installed creations.
- Open a creation for its gallery, settings, GitHub links and artist credits.
  Support links are optional and go directly to the creator's page.
- **Subscribe & download** is free. Subscribed packages check for updates at
  startup and every 15 minutes while MagicShelf runs, including while Off.
- On/Off controls running the creation separately from its subscription.
  Unsubscribing keeps the installation and saved data; removing it also cancels
  the subscription and keeps saved data.
- New permissions require review. Failed updates retain the previous working
  version and data; **Restore previous version** supports manual recovery.
- **Return creations home** returns active creations to their shelf slots.

**Pocket Clock** is an optional developer example, excluded from the default shelf.
MagicShelf is the single dashboard entry; open a creation and choose **Configure creation** to manage it.
The existing Android phone and Digivice can be adopted on a migrated installation.
They show **Installed locally** with real previews and controls. Downloadable
packages for these two integrations are not published yet, so their pages do not
advertise a working subscription or download. Jojogape's artist link currently
opens [the supplied X profile](https://x.com/jojogape).
Off hides the devices and suspends their game/Android processes, including the
Android container, so they stop executing and producing audio. On resumes the
same session in its shelf slot. Their capture connections and memory stay
allocated to preserve the Android session and pet. Disabled backends no longer
autostart with SteamVR. Local adapter capability v2, systemd cgroup v2 freezing,
and Podman for Android are required. MagicShelf does not distribute
the Android image, the Digital Partner game, or third-party Digivice artwork.

The shelf appears beside Steam's launcher and hides while the launcher is closed
or another dashboard app is active. Native expanded sidebar labels cover the
shelf. Modules can implement their own pick-up and room behavior.

The local phone and Digivice interaction update adds a small grab bar: hold the
trigger on the bar or outer frame, then use that controller's thumbstick to push
the creation away or pull it closer. Release to save its position. See the
[local device upgrade](integrations/local-devices/README.md#grab-and-depth-controls)
for installation and validation; this update is separate from the v0.1.3 download.

The [dock recovery update](integrations/local-devices/README.md#dock-recovery)
returns creations home on position/layout resets. Hold and shake a creation to
send it home, or bring it over the dock and release when its grab bar turns green.
Each creation returns to its assigned slot.

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
bash tools/test_storefront.sh
bash tools/test_dashboard.sh
bash build.sh
```

Build requirements: C++17, pkg-config, Cairo, json-c, EGL/GLES development files,
and the matching SteamVR `libopenvr_api.so`. The vendored OpenVR header is under
Valve's BSD license; see [OPENVR-LICENSE.txt](OPENVR-LICENSE.txt).

The legacy browser interface is available only through the explicit
`magicshelf web` diagnostic command. It is not the app launch path.

Release artifacts are written to `dist/`. Build on the target architecture.
The build creates the framework archive, catalog, verified bootstrap installer,
and downloadable `.desktop` launcher. Creations build and publish their own
`.magicshelf` packages; see [Creating a creation](docs/CREATING.md).

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
