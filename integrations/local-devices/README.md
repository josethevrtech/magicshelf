# Existing device shell upgrade

Current creation source now lives in independent repositories:
[Android Phone](https://github.com/josethevrtech/magicshelf-android-phone) and
[Digivice](https://github.com/josethevrtech/magicshelf-digivice).
The patch stack below records the original migration and remains useful for
capture-preserving deployment. Make new device-specific changes in the creation
repository and shared interaction changes in the pinned MagicShelf SDK.


This patch upgrades the pre-existing phone/Digivice shells from adapter capability
1 to 2. It contains no models, game files or Android image. It is separate from
MagicShelf module API v1.

For an existing source tree with the single-icon MagicShelf integration, apply
`capture-lifetime.patch` using `patch -p1`, then run its `build.sh` on the Frame.
Back up the installed binaries, source, settings and capability marker before
replacing either binary. Install the rebuilt phone and Digivice binaries together,
then write `2` to `magicshelf-api-version`. Restart only their visual services.

If a gamescope capture stream has already disappeared, its Android runtime must
be restarted once to recreate the display source. Installed Android data remains
in place, but running apps restart. Do not restart SteamVR for this migration.

Off hides an adapter without disconnecting its capture, then the manager freezes
its backend services. Android also needs `podman pause` on the exact
`lepton-courage-tablet` container: it runs outside the gamescope service's cgroup.
This stops execution and audio without changing volume/mute preferences or
discarding the open apps and pet. On thaws the services, unpauses Android and
sends `--dock` to the same shell. Backend autostart links are disabled with Off;
the enabled shell's dependencies start them when needed. Manager startup
reconciles both paused and resumed states. Failed toggles restore the previous
state. Memory remains allocated; packaged modules retain stop-on-disable behavior.

## Grab and depth controls

After the capture-lifetime patch, apply `grab-controls.patch` with `patch -p1`
from the existing device source tree, then run `build.sh`. This updates both
the Android Phone and Digivice. The shared placement/renderer helpers in
`native/compat` contain the same changes for future creations.

- Hold the trigger on the outer frame or the small bar beneath the creation.
- Move the controller to place and rotate it. While holding, push the same
  controller's thumbstick forward to move it away, or pull back to bring it closer.
- Release the trigger to save its room position. Return to dock still restores
  the creation to its shelf slot without changing its normal size.
- The bar appears while the dashboard is open, while pointing at the creation,
  or during a grab. It highlights when targeted or held, and is hidden in wrist mode.
- Android screen taps, settings and scrolling remain separate from grabbing.
  After a grab, centre the thumbstick before scrolling again.

This follows SteamVR's trigger-and-thumbstick interaction. The bar is rendered
within the transparent stereo model, not a new dashboard window. Valve's
`MinimalControlBar` would control the underlying head-facing overlay, whose pose
this renderer updates every frame; it cannot simply be enabled to move the model.
Depth is frame-rate independent, with a dead zone, a bounded time step after
tracking interruptions, and a 0.2–5 metre range from the grabbing controller.
Existing placements outside that range move back gradually rather than snapping.

On Frame, the dashboard can leave the analog action inactive while delivering
`VREvent_ScrollSmooth` to the overlay. During a grab, those integrated deltas
move depth along the selected ray. Only the grabbing controller is accepted;
stale events are discarded and queued movement is cleared on release. An active
analog action takes precedence, so the two paths cannot double the movement.

Run `bash tools/test_grab.sh` in the MagicShelf checkout for both geometry profiles.
The device tree's existing build also exercises screen mapping, room grabs, dock
placement and configuration parsing. The regression test replays Frame scroll
values with inactive analog input for both hands, including release, event
batching, stale input and simultaneous action/event delivery. Live controller
feel still needs a headset test.

For input diagnosis, create `grab-debug` beside the binaries before launching a
shell. While grabbing, it logs the selected input path, depth and movement at
most once per second. Remove the marker to disable diagnostics on the next launch.

Back up the installed binaries, modified source and both settings files before
deployment. Restart only visual services that were already running. Keep their
PipeWire sources connected during replacement: compile `capture_hold.cpp` with
the device tree's `src` include directory and `pkg-config --cflags --libs
libpipewire-0.3`. It takes source node, width, height and a readiness-file path;
it reports readiness after negotiating a streaming connection and exits after at
most 90 seconds. Sleeping or unchanged displays may produce no new frames.
Start it under a memory-limited user service, require readiness before restarting
a shell, then stop it only after the replacement shell negotiates capture.
Verify live frames after waking the headset.
Android, its input bridge, SteamVR and the pet should retain their process IDs.

## Dock recovery

Apply `dock-recovery.patch` after `grab-controls.patch`, then rebuild both shells.
Use the same capture-preserving deployment procedure above.

- **Reset position & size** restores the default size/yaw and returns the creation
  to its assigned dock slot. SteamVR position-origin, room-setup and dashboard
  reset events also return visible creations home. Spatial shelf configuration
  changes return creations to their current slots; identical or invalid rewrites
  and appearance-only changes do not.
- While holding the trigger, shake the controller back and forth several times
  to return the held creation home. Recognition needs four direction reversals,
  at least 4.5 cm per stroke, within 1.6 seconds. It ignores initial pickup motion,
  slow adjustment, small jitter, tracking jumps and thumbstick depth changes.
- Move a held creation over the visible dock. A green grab bar and a short pulse
  indicate that releasing the trigger will snap it home. The entire dock accepts
  drops; each creation retains its assigned slot and saved normal size. Hidden
  docks do not catch drops. Returning home clears grabs, app touches and stale
  room placement. If the launcher is closed, the creation waits on its shelf.

Run `bash tools/test_dock_recovery.sh` for both device profiles. It covers rotated,
scaled and curved docks, drop bounds, shake recognition at multiple frame rates,
noise rejection, reset event routing and configuration reload behavior.

## Keep the pet capture separate from Android

Apply `capture-identity.patch` in the current device source tree after the dock
recovery patch. Apply `android-source-identity.patch` separately inside
`~/Applications/AndroidTablet`. Both publishers now record the source's
PipeWire `object.serial`, and the shells use `target.object` to select that exact
source. `node.dont-fallback` prevents WirePlumber from substituting another
video source when the requested one disappears; `node.dont-reconnect` prevents
silent switching after a disconnect. The capture callback also rejects dimensions
other than its profile's expected size before accepting any pixels.

This fixes the Digivice displaying Android Home after an earlier lost game
capture: the saved node ID referred to a WirePlumber client, and the session
manager fell back to the remaining Android video source. Game input still went
to the pet display, making the visible Android screen appear unresponsive.

Rebuild the pet binary using the existing build command. If its source is already
missing, stop the pet shell and game backend, remove `private-source.json`, then
start both services to create a new game source. Otherwise use the documented
capture-holder procedure during shell replacement. Android and SteamVR do not
need to restart. A reset of pet saves is **not** part of this fix; the user
separately requested a fresh game on October 21, 2026.

Compile `capture_identity_probe.cpp` with the device `src` include path and
`pkg-config --cflags --libs libpipewire-0.3`. It accepts node ID, expected width,
expected height, object serial, and `accept` or `reject`; an optional final path
writes a successful capture as PPM. Exercise a live pet source (480 × 1046), a
nonexistent serial (must produce zero frames), and the Android source while
requesting pet dimensions (must reject 720 × 1600). Keep each source's normal
shell connected throughout testing so the probe is not its last capture client.

Live validation on October 21: correct pet frames received; nonexistent serial
rejected without fallback; Android dimensions rejected for the pet profile;
three MagicShelf Digivice Off/On cycles retained all five monitored process IDs
and the game feed. No-death, music-off and 12-hour patches verified by hash.

## Digivice text entry

Apply `pet-keyboard.patch` after `capture-identity.patch` in the device source
tree, then rebuild the pet binary. Use the capture-holder procedure above to
restart only `digitalpartner-vr.service`; the running game and entered name
remain intact. The Android binary does not need replacement for this fix.

Digital Partner PC 1.1.9A draws its own text boxes. Its tamer-name and nickname
gesture handlers call GameMaker's mobile `keyboard_virtual_show`, which has no
effect in the Windows runner. There is no native X11 edit control to report
focus. The shell now recognizes the shared name-input sprite's blue outer
border, cyan inset and pale fill when tapped, then opens SteamVR's keyboard
after releasing the game tap. Recognition uses capture pixels before VR
brightness adjustment and does not inspect the user's text or depend on the
box's screen position. Other text styles retain the **VR keyboard** button in
the device's settings as a manual fallback.

Pending requests are cancelled by another game tap, settings, grabbing or
hiding. The field is checked again before opening. Closing the keyboard does
not reopen it until another tap. Keyboard characters are processed only from
this device's overlay queue, avoiding duplicate global events. Failure to open
a busy keyboard is logged without terminating the shell. The shell tracks
keyboard ownership so closing its settings/device cannot dismiss another
creation's keyboard. Close the keyboard after typing, then use the game's OK
button; opening or dismissing the keyboard does not submit a name.

Build `pet_text_input_test.cpp` with C++17 and run it with a captured tamer-name
PPM followed by one or more non-input game frames (480 × 1046). This checks real
field edges and outside taps, typed contents, a relocated widget, a damaged
border, wrong capture dimensions, negative game screens, and deferred-request
cancellation. The header in this directory is identical to the one in the patch.

October 21 deployment: recognition tests passed with the live name screen,
fresh-game title screen and pet screen; the pet build and Android-profile syntax check passed.
The replacement shell reconnected to the same game capture. Game, Android,
Android bridge, Android shell and SteamVR process IDs were unchanged.
The controller tap was logged as a text-field hit, SteamVR accepted the keyboard
request, and the user progressed to the egg screen with a non-empty tamer name
saved. The visual service reported zero restarts during that test.
