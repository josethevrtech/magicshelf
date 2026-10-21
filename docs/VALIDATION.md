# Validation — October 21, 2026

MagicShelf 0.1.3 is installed on the Steam Frame (Linux aarch64).

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
