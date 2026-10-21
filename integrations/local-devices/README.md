# Existing device shell upgrade

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

Off now hides an adapter without disconnecting its capture. On sends `--dock`
to the same process. Turning off a device keeps its memory allocated; packaged
modules retain normal stop-on-disable behavior.
