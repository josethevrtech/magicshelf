# Validation — October 21, 2026

MagicShelf 0.1.3 is installed on the Steam Frame (Linux aarch64).

## Local Off/audio fix — October 21, 2026

The manager hotfix is installed as
`~/.local/share/magicshelf/releases/0.1.3-local-off-pause-20261021`; the original
0.1.3 directory is retained and unmodified. This is a local deployment, not a
new published GitHub release. Native binaries, the recent capture-identity and
Digivice keyboard fixes, and user save files were not replaced.

The previous Off implementation only hid the shell. Digital Partner kept
producing audio, and Android kept executing in a separate Podman scope. Off now
freezes the relevant backend services and pauses Android's exact Lepton
container. It disables their independent SteamVR autostart links. On resumes
the same processes and returns the creation to its dock. Capture consumers stay
connected and memory remains allocated; this is suspension, not termination.

- All 38 Python framework, installer and release tests pass, including creation
  isolation, resume after manager restart, missing-shell reconciliation,
  idempotent container handling and recovery from failed Off/On operations.
- Two live Off/On cycles per creation passed through the manager API. Both
  capture sources delivered frames after resume. The static Android home screen
  needed a diagnostic SurfaceFlinger repaint for the fresh capture probe; no app
  was restarted or navigated away from its current screen.
- With both Off, all three backend service cgroups and Android's container
  cgroup accumulated zero CPU microseconds over a two-second sample.
- The game's unmuted stream produced 98,304 audio samples with peak amplitude
  zero while Off. The initial emergency mute was removed; volume and mute
  preferences are not part of the permanent fix.
- SteamVR, the library, both shells, all backends and Android's container kept
  their original process IDs. Capture nodes 188 (game) and 181 (Android), source
  metadata and service restart counts were unchanged. Manager restarts reapplied
  the saved Off state successfully. SteamVR itself was not restarted.
- The user confirmed: **Silent when Off; both resume normally.**

## Published 0.1.3 baseline

- 30 Python tests pass, covering package integrity, compatibility, safe extraction,
  module save retention, update recovery, readiness, installer rollback and releases.
- Native ARM host build passed (211 MiB peak memory). Both device shells and their
  geometry/configuration tests passed (270 MiB peak build memory).
- The real generated systemd unit passes systemd-analyze verification.
- Installation and the 0.1.1-to-0.1.3 upgrade succeeded with backups. SteamVR,
  Android, its bridge and the pet retained their process IDs. Device sizes,
  brightness, yaw and saved room poses were preserved.
- Read-only OpenVR inspection confirms the sole MagicShelf dashboard entry,
  both device overlays, and absence of the individual device dashboard overlays.
- Library Open actions succeeded for both adapters; Return toys home succeeded.
- Pocket Clock was installed and reported readiness during development, then
  removed. It is an optional example and is excluded from the default package
  and official catalog.
- The user saw the native library in the headset. Final visual confirmation of
  the revised single-icon library remains a human check.

Only Linux aarch64 is advertised by this release. New clean-machine installs and
third-party modules need their own validation. API v1 and rollback checks reduce
compatibility failures; they do not guarantee arbitrary native code is bug-free.
Modules run as trusted user processes, not in a security sandbox.

Capture recovery fix: after a lost gamescope PipeWire stream, the Android runtime
and its dependent bridge were restarted once. Three subsequent Off/On cycles
kept the phone shell, Android, bridge, SteamVR and pet process IDs unchanged;
the Android Video/Source node remained running. Adapter Off now uses --hide
without disconnecting capture. On returns the same device to its shelf slot.

## Local creation grab update — October 21, 2026

The updated phone and Digivice binaries are installed on the Frame separately
from the published 0.1.3 release. They add a contextual grab bar and thumbstick
push/pull while holding the trigger. The model stays three-dimensional.

- Both native builds passed. Existing screen mapping, settings hit testing,
  room placement, dock geometry and configuration tests passed for both profiles.
- New depth tests pass for both profiles: selected-ray direction, rotation
  preservation, release, near/far limits, frame-rate independence, wake-up time
  clamping, invalid input and separation of the grab handle from screen controls.
- All 30 Python framework/installer/release tests pass.
- Both grab-bar previews rendered successfully on the Frame's GPU.
- The running Android shell was replaced while a temporary PipeWire consumer
  held its source open. The source stayed running and the new shell reported
  `Android screen received`. The temporary consumer was then removed.
- SteamVR, Android, its bridge and the pet retained their process IDs. Both
  settings files were byte-for-byte unchanged. The inactive Digivice shell was
  updated on disk and left inactive.
- The user's first headset test confirmed grabbing, but depth failed for both
  hands. Tracing showed inactive analog actions and live overlay smooth-scroll
  events. The corrected build now consumes that event path during grabs.
- Regression tests pass for both controller IDs with recorded Frame scroll
  magnitudes, inactive actions, event batching, stale/wrong-hand input, release
  and duplicate action/event delivery. Both ARM shell builds and their existing
  geometry/configuration checks pass again.
- The corrected shell negotiated capture and received Android frames. Backend
  process IDs and both settings files remained unchanged during installation.
- The user confirmed depth movement, but reported reversed directions. Live
  traces showed scroll-driven movement and saved placements for both hands.
  The scroll sign was corrected so forward pushes away and back pulls closer.
  Both profile regression tests and both ARM builds passed; the corrected
  binaries were installed with capture continuity and settings preserved.
  The user subsequently confirmed the corrected movement feels much better.

The installation backup is under the Frame's
`~/Applications/DigitalPartner/vr/backups/grab-controls-20261021T183831Z`.
The backup before installing the Frame scroll fix is
`~/Applications/DigitalPartner/vr/backups/grab-controls-20261021T184846Z`.
The backup before correcting scroll direction is
`~/Applications/DigitalPartner/vr/backups/grab-controls-20261021T190614Z`.

## Local dock recovery update — October 21, 2026

The phone and Digivice shells now return home on position/size reset, recognized
SteamVR origin/dashboard reset events and spatial shelf configuration changes.
They also support shake-to-dock while held and release-to-dock proximity snapping,
with a green grab bar and haptic feedback. Returning home clears active input and
the old room pose while retaining normal size except on a size reset.

- Recovery tests pass for both profiles: flat/curved, rotated and scaled docks;
  one to sixteen slots; drop bounds; shake recognition at 30/45/90/120 Hz;
  rejection of jitter, slow motion, tracking jumps and invalid samples; reset
  event classification; and meaningful versus no-op configuration reloads.
- Both ARM shell builds and existing screen, placement, dock and configuration
  checks pass. Grab/depth regressions pass for both profiles.
- The docking-indicator shader rendered on the Frame GPU. Both binaries were
  installed; only the active phone shell restarted. Capture stayed connected to
  node 181 and the phone reported `Android screen received` afterwards.
- SteamVR, Android, its bridge and the pet kept their process IDs. Both settings
  files were unchanged during installation. The inactive Digivice stayed inactive.
- During the user's live test, the phone received SteamVR standing-position
  reset event 808 and logged `reason=VR reset`. Subsequent grabs logged
  `reason=shake` and `reason=drop`, confirming all three recovery paths executed.
  The user confirmed all three actions work well in the headset. Other SteamVR
  reset controls depend on which public events they broadcast.

The pre-update backup is
`~/Applications/DigitalPartner/vr/backups/grab-controls-20261021T191752Z`.


## Local storefront 0.2.2 — October 21, 2026

The native SteamVR dashboard and desktop browser now present a free creation
storefront with screenshot galleries, per-creation settings, project links and
artist/support credits. Jojogape's supplied X profile is included. The existing
phone and Digivice are explicitly marked local installations; no download or
subscription is offered for their unpublished packages.

- All 53 Python framework, installer, contract and subscription tests pass on
  the development machine and on the Frame. Subscription tests install real
  fixture archives, preserve Off state and saves, persist across manager restart,
  apply updates, require review for new permissions, retain old versions on
  failed/offline downloads, pin catalog sources and cancel updates on removal.
- Catalog image metadata cannot select local filesystem paths; only built-in
  previews use local assets. The regression test passes.
- The ARM native build and standalone storefront test pass. Native checks cover
  collection pagination, navigation, settings, credits, links, subscription
  confirmation payloads and non-overlapping controller hit targets.
- Browser checks covered searching, detail/settings navigation and On/Off in an
  isolated fixture. Both state changes appeared correctly; no console errors
  were reported. The responsive single-column detail view was inspected.
- The verified local 0.2.2 bundle was installed using the regular per-user
  installer. Only the manager and MagicShelf dashboard restarted. SteamVR, the
  phone/Digivice shells, game backend, Android backend and paused Android
  container retained their process IDs. Both creations remained Off; backend
  services stayed frozen and the container stayed paused.
- Both MagicShelf services are active with zero automatic restarts. Four built-in
  screenshots return HTTP 200 as PNG. The live native dashboard renders at
  2560 × 1800; its image was copied for visual verification.

Backup: `~/.local/share/magicshelf/install-backups/storefront-20261021T203941Z`.
The previous `0.1.3-local-off-pause-20261021` installation remains available for
rollback. This is a local installation, not a published GitHub release.

The user confirmed the new storefront layout and controls work, then requested a
larger opening size. The dashboard now opens 50% wider (1.8 m instead of 1.2 m)
and renders at twice the resolution in each dimension. Input retains the same
logical coordinates so existing controller hit targets remain aligned. The live
PNG measures 2560 × 1800 and OpenVR reports a 1.8 m width. Dashboard memory use
is about 50 MiB, below its 192 MiB limit. The user confirmed the larger starting
size is comfortable and the text and buttons remain correctly aligned.


## Native navigation polish 0.2.4 — October 21, 2026

The dashboard previously encoded a new full-screen PNG and called
`SetOverlayFromFile` for each state or navigation change. It now keeps one
EGL/GLES texture alive, uploads changes in place, caches decoded gallery images,
and repaints only affected controls for hover and press feedback. Trigger release
activates a control; moving away or losing focus cancels the press. Tabs and
collection navigation remain available while manager actions are pending. The
approved 1.8 m width and 2560 × 1800 resolution are retained.

MagicShelf targets SteamOS and Steam Frame only. The desktop shortcut and
`magicshelf open` now start/show the native SteamVR dashboard. The previous browser
UI is an explicit `magicshelf web` developer diagnostic.

- All 54 Python tests pass locally and on the Frame, including a regression check
  that the app launcher selects the native dashboard.
- Native navigation/input checks pass locally and on ARM: release targeting,
  duplicate release, cancellation, focus loss, changed targets, and navigation
  while busy. Existing pagination and hit-target checks also pass.
- Offscreen EGL tests verify full/partial upload colors and vertical orientation
  against every expected pixel through 100 updates of the same texture.
- An ARM benchmark of twenty full page changes averaged 35.7 ms for drawing and
  upload (133.9 ms cold peak), before compositor submission. This is a rendering
  measurement, not end-to-end controller latency.
- The first GPU deployment hit the previous 192 MiB service limit during SteamVR
  graphics interop initialization. The final installer gives the native dashboard
  a 512 MiB limit and 64 MiB swap cap; the manager remains at 192 MiB. Temporary
  runtime overrides were removed. Final service operation has zero restarts and
  measured approximately 390–401 MiB of memory during navigation.
- Live rendering recorded 94 submissions with one application texture allocation,
  including many control-only updates (a sampled update took 2.3 ms). No
  `library-*.png` frame files are generated. PNG export is explicit diagnostics
  only. The native launch command opened the dashboard successfully.
- SteamVR, both creation shells, the game, Android and its bridge retained their
  process IDs. Both creations remained Off, their backend services frozen and
  Android's exact container paused. Capture sources 181/2451 and 188/2630 remain
  running with the same identities.

Backup: `~/.local/share/magicshelf/install-backups/native-polish-20261021T205412Z`.
Version 0.2.2 remains available for rollback. This is installed locally; no GitHub
release was published. The user tested creation/tab navigation and controller
hover/trigger interaction in the headset and confirmed: **smooth, no flashing**.

## Independent creation repositories — October 21, 2026

MagicShelf 0.3.2 is installed on the Frame. The Phone and Digivice now have
independent source repositories, pinned SDK dependencies, ARM build workflows,
immutable release packages and subscription catalogs:

- <https://github.com/josethevrtech/magicshelf-android-phone>
- <https://github.com/josethevrtech/magicshelf-digivice>

The framework source and previous native storefront improvements are published
in <https://github.com/josethevrtech/magicshelf/pull/1>. The public MagicShelf
installer remains 0.1.3; 0.3.2 is a tested local installation, not a published
framework installer release. The creation releases document this requirement.

- All 59 Python tests pass. Native grabbing/depth, dock recovery and storefront
  control checks pass. Both independent ARM workflows build and package their
  creations. A generated starter creation also builds and packages on the Frame.
- Each API 2 package owns its shell and backend lifecycle, configuration and
  docking commands. The old adapter services are disabled. Off stops the owned
  processes; the Phone also stops its exact Android container. The user confirmed
  both creations respond, configure, grab/move in depth, return to the dock, and
  are silent when Off.
- The user authorized fresh installations without preserving creation saves.
  New package data/runtime directories were used. Existing game/model inputs were
  imported locally; they were not published. The package builder explicitly
  limits included assets; a packaging smoke check verified imported game/model
  files are excluded even when present in the local source tree.
- Both 0.2.2 packages downloaded through their public GitHub catalogs and remained
  subscribed. Updating either creation left the other's process ID unchanged.
  Each creation supplies its own gallery and metadata.
- Normal removal deleted each installed package and generated service, canceled
  its subscription, and left the other creation running. Re-subscribing downloaded
  the package again; On and Configure succeeded. This second removal test used
  the normal uninstall behavior, which retains data.
- Digivice memory testing caught a combined game/Proton/shell allocation above
  1 GiB. Its API 2 manifest now allows 2 GiB; stable observed use is about 1.5 GiB,
  with no automatic restarts. Phone use is about 683 MiB under its 1 GiB limit.
- Repeated startup exposed an intermittent Digivice first-capture stall despite
  a running game and streaming PipeWire link. A second connection received frames.
  Digivice 0.2.3 adds a bounded first-frame retry that keeps the old consumer alive
  until the replacement receives a frame. Tests cover timing, source identity,
  failed candidates and retaining a consumer throughout replacement.
- Digivice 0.2.3 passed its independent ARM build/release workflow, downloaded
  through the existing subscription, and delivered live frames on three
  consecutive restarts. Phone's process remained unchanged throughout.
- A temporary test shim withheld every frame on the first connection while
  leaving its consumer connected. The installed public 0.2.3 binary opened a
  replacement, logged recovery and received live game frames. The shim and
  systemd override were removed, and a normal final start received frames.
  Both creations were returned to the dock; Phone stayed running throughout.

Local migration backup:
`~/.local/share/magicshelf/install-backups/independent-creations-20261021T172121`.
Per-creation runtime data, caches and externally supplied inputs are separate
from immutable package directories. Android's opaque user-namespace files are
outside ordinary framework data snapshots; see the API 2 rollback limitations
in [CREATING.md](CREATING.md).

## Collection cleanup and app settings 0.3.3 — October 21, 2026

The native app now uses a black background and blue accents. Discover has a
single **Explore the Collection** heading; pricing badges and promotional free
copy are removed. The main title is **MagicShelf**, with developer and project
credits moved to Settings. The diagnostic browser UI follows the same wording.

Settings exposes bounded dock size, spacing, opacity, visibility, position,
angle and lean controls, plus dashboard width and starting view. Changes persist
in the existing layout file without modifying the module API or requiring new
creation builds. Geometry changes and shelf/placement resets return active
creations home; app preferences and opacity changes do not reposition them.

- All 64 Python tests pass locally and on the Frame, including persistence,
  atomic rejection of invalid settings, scoped resets and credit link validation.
- Native control checks pass on both architectures. The new settings pages have
  non-overlapping hit targets and valid action payloads. Settings previews and
  a live Discover capture were inspected at 2560 × 1800.
- The persistent texture test passes on the Frame, including full and partial
  upload colors, orientation and 100 updates. Live rendering still reports one
  application texture allocation.
- The verified ARM bundle installed successfully as 0.3.3. Live RPC checks
  changed settings, restarted the manager, verified persistence, exercised all
  three reset groups and restored the previous preferences. The original dock
  objects and anchor were preserved. OpenVR reports the restored 1.8 m app width
  and 1280 × 900 logical input coordinates.
- SteamVR retained PID 2571. Both MagicShelf services are active with zero
  automatic restarts. The creations were uninstalled at the start of this work
  and remain uninstalled; this update did not alter their installation choices.

Controller feedback on these new controls is pending the user's headset check.
This is a local installation; the public framework installer remains 0.1.3.

## Collection power controls and installation feedback 0.3.4 — October 21, 2026

Installed creation cards now expose On/Off directly in Discover and My Shelf,
with the same control at the top of a creation's page. Card navigation and power
have separate hit targets. Download progress reports actual received bytes and
percentage, followed by checking, installing and ready states. Downloads already
installed automatically; the UI now consistently calls the result **Installed**
and explains how to turn it on. Install reviews explain each declared permission
in everyday language while preserving the underlying approval values.

- All 69 Python tests pass locally and on the Frame. New coverage checks actual
  byte counts, download limits, progress publication, automatic installation,
  corrupt-download recovery, and permission explanations for installs/updates.
- Native checks pass on both architectures for direct card toggles, correct
  creation IDs and On/Off values, navigation without activating power, disabled
  actions while busy, pagination and non-overlapping hit targets. GPU texture
  tests still pass. Native previews of cards, progress and all four permissions
  were visually inspected; the diagnostic JavaScript parses successfully.
- The verified 0.3.4 ARM bundle installed on the Frame. The Phone was running
  before and after installation with PID 646474; SteamVR retained PID 2571.
  Existing preferences remained unchanged.
- A live Digivice subscription downloaded its public 0.2.3 package, reporting
  0, 65,536 and 92,354 bytes. It then installed automatically and reached the
  complete state, subscribed and Off, without a second installation action.
  The temporary installation was removed to restore the user's initial choice;
  the Phone and SteamVR kept their process IDs throughout. Saved data was kept.

Headset confirmation of the new card controls and permission wording is pending.
This is a local installation; the public framework installer remains 0.1.3.

## Compact power switches and Android preview 0.3.5 — October 21, 2026

The user's live capture confirmed that the combined On/Turn off button was too
large and the Phone gallery showed a browser. Collection cards and detail pages
now use a compact switch labeled only On or Off, with a 116 × 48 logical hit
target. The duplicated power button inside the detail Settings tab is removed.
The diagnostic browser UI uses the same switch and retains accessible state.

- All 69 Python tests and native storefront control checks pass locally and on
  the Frame. Existing tests cover toggle values, creation identity, navigation,
  busy states and non-overlapping hit targets. Diagnostic JavaScript parses.
- The ARM build and normal installer succeeded. App preferences were unchanged,
  and the Phone kept its running process during the framework upgrade. Both
  MagicShelf services remained active with zero automatic restarts.
- Phone 0.2.3 independently publishes a gallery-only update: an actual Android
  home-screen capture rendered in the original phone model. Its runtime and
  permissions are unchanged. ARM build and release workflows passed, and the
  public release includes its package, checksums and catalog.
- The existing subscription downloaded and installed Phone 0.2.3 automatically.
  It remained enabled, running and subscribed; the new screenshot was cached.
  Digivice remained uninstalled. SteamVR was not restarted.
- A live 2560 × 1800 dashboard capture confirms the compact On switch and Android
  home-screen preview on the collection card. Native detail previews were also
  inspected. Headset comfort with the smaller switch remains a user judgment.

MagicShelf 0.3.5 is installed locally; the public framework installer remains
0.1.3. Public creation releases are Phone 0.2.3 and Digivice 0.2.3.

## Discover navigation cleanup 0.3.6 — October 21, 2026

Removed the upper-right **Return creations home** button from the native app and
diagnostic browser UI. Discover remains the collection's home navigation: its
existing handler clears the selected creation and pending review and returns to
page one. The browser navigation also resets its category and search filters.

- All 69 Python tests pass locally. Existing native navigation and hit-target
  checks pass locally and on the Frame; diagnostic JavaScript parses.
- The ARM build and verified installer succeeded. A live 2560 × 1800 capture
  confirms the upper-right button is gone.
- App preferences, creation versions, subscriptions and On/Off states were
  unchanged. Android Phone (Virtual) 0.2.5 remained running and Smartphone
  Digivice 0.2.4 remained Off. Creation and SteamVR process IDs were unchanged.
  Both MagicShelf services are active with zero automatic restarts.

MagicShelf 0.3.6 is installed locally; the public framework installer remains
0.1.3. Category browsing for the native collection is future work.
