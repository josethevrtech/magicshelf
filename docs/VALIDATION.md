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
