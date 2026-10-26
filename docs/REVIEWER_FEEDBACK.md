# Reviewer follow-up (0.3.20)

MagicShelf manages creation installation, On/Off, subscriptions, updates,
rollback and removal. Creation-specific settings belong to each creation.
The creation page now says Manage and no longer opens device settings. The
diagnostic web view follows the same boundary.

Long About descriptions have Previous/Next pages instead of a fixed five-line
cutoff. The native panel has an explicit Close panel action and requests the
SteamVR minimal control bar and close control. Its application registration
enables SteamVR auto-launch, in addition to the existing user service.

The SDK retains nearest-neighbor magnification for pixel art while using
trilinear mipmaps for minification. This reduces aliasing of small or angled
Digivice screens without changing their game pixels or saves.

The companion creation branches add grip pickup and a startup room-placement
fallback when the dashboard dock is unavailable. The phone owns wrist placement
and Android text-size controls. These are creation changes, not host settings.

Validation: 169 Python tests; native storefront, dashboard texture, grab and dock
recovery checks. Storefront tests exercise every About page and verify that
creation management contains no device-settings action. An ARM64 source build,
verified local installation and rendered dashboard heartbeat succeeded on the
development Steam Frame. This is not a frametop or physical controller test.

SteamVR's public dashboard API adds a dashboard application. Frametop and Steam's
panel pinning are controlled by those environments; this update does not claim
automatic insertion into frametop's desktop-window list. A native VR overlay
does not have ordinary desktop window decorations. The explicit panel close
action remains available when the environment omits SteamVR's control bar.

Physical grip/button routing, wrist comfort and perceived shimmer still need
headset verification. Frametop hand tracking is a separate integration and is
not advertised by this controller update.
