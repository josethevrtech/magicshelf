# Exclusive testing readiness

MagicShelf 0.3.14 provides a graphical installer, automatic creation setup and an
in-app framework updater for Steam Frame. Creations retain independent repositories
and subscriptions. Creations require no payment or separate MagicShelf account.

## The tester experience

1. Download and open **Install.MagicShelf.desktop** in Desktop Mode. The installer
   shows progress, verifies its download and offers **Open MagicShelf** when ready.
2. Choose a creation, read its plain-language permissions and select
   **Subscribe & download**. Installation finishes automatically.
3. MagicShelf shows **Setting up** while Steam downloads any missing support
   files in the background. Already installed support is reused. Existing
   creations with incomplete setup have a **Set up** button to start this process.
4. Turn the creation On. Configure, Off and the shelf controls remain on its page
   and collection card.
5. Creation updates download in the background and install when that creation is
   Off. MagicShelf updates download separately and install after its panel has
   been closed for 30 seconds, without interrupting running creations or SteamVR.
   **Update and reopen** is also available for an immediate update. No repeat
   desktop installation is needed. Failed updates keep the working version and
   wait for a manual retry rather than repeatedly restarting.

Android Phone (Virtual) 0.2.6 declares Steam's Android support and
prepares its private runtime safely. Smartphone Digivice 0.2.5 bundles its game
and model with permission confirmed by the project owner; no import or model
conversion is required. MagicShelf installs its two required Steam support
packages automatically through the running Steam client. If Steam cannot complete
setup, the page offers **Retry** and an **Open Steam** fallback.

## Recovery behavior

Downloads are bounded, checked and retried after temporary connection failures.
Support setup runs without blocking browsing, persists across manager restarts,
and retries temporary failures up to three times. Steam command acceptance alone
never counts as success: installed state and required files must both be present.
Creation updates preserve module data and recover interrupted installations.
Restore previous holds the replaced version instead of immediately reinstalling
it. A bad first start after an update installed while Off restores the previous
creation. New permissions require explicit review.

Framework installation verifies its file index, the new manager's version, and a
rendered frame from the new native process. Failure restores the previous release.
An independent worker survives manager restarts, and a journal handles interrupted
worker execution. Startup detects unfinished framework work after a device restart.
The graphical installer offers retry and keeps a local diagnostic log.

## Validation and first tester checks

Automated checks cover empty-home requirement detection, Steam download progress,
malformed requirements, verified framework downloads, archive tampering and path
escape, interrupted update recovery, native setup/update hit targets and creation
lifecycle behavior. See [VALIDATION.md](VALIDATION.md) for actual device results.

A prepared development Frame is not a factory-fresh device. Before expanding the
invite group, have one tester complete installation and first launch on a separate
supported Frame with their own Steam account. Check automatic support downloads, opening both
creations, Configure, grab/depth, returning to the dock, silence while Off and a
normal reboot. Do not describe simulated recovery tests as physical power-loss or
fresh-hardware testing.

Repeatable checks: `python3 -m unittest discover -s tests -v`,
`bash tools/test_storefront.sh`, `bash tools/test_dashboard.sh`, and
`python3 tools/test_update_lifecycle.py --live` on a Frame with SteamVR running.
The lifecycle probe uses an isolated disposable creation and real systemd/readiness
RPC, with local package transfers. It leaves the user's collection alone.
