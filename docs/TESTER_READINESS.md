# Exclusive testing readiness

MagicShelf 0.3.10 provides a graphical installer, guided creation setup and an
in-app framework updater for Steam Frame. Creations retain independent repositories
and subscriptions. Every creation is available without payment or an account.

## The tester experience

1. Download and open **Install.MagicShelf.desktop** in Desktop Mode. The installer
   shows progress, verifies its download and offers **Open MagicShelf** when ready.
2. Choose a creation, read its plain-language permissions and select
   **Subscribe & download**. Installation finishes automatically.
3. If **Set up** appears, select it and choose **Continue in Steam** for the
   missing support download. Finish Steam's normal dialog and return to MagicShelf.
   The app detects download progress and completion; no folder selection or
   terminal commands are needed.
4. Turn the creation On. Configure, Off and the shelf controls remain on its page
   and collection card.
5. Creation updates download in the background and install when that creation is
   Off. MagicShelf updates download separately and offer **Update and reopen**.
   A framework upgrade leaves running creations and SteamVR running.

Android Phone (Virtual) 0.2.6 guides installation of Steam's Android support and
prepares its private runtime safely. Smartphone Digivice 0.2.5 bundles its game
and model with permission confirmed by the project owner; no import or model
conversion is required. It guides installation of the two required Steam support
packages. Steam may still require the user to confirm a download.

## Recovery behavior

Downloads are bounded, checked and retried after temporary connection failures.
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
supported Frame, including any Steam download prompts. Check opening both
creations, Configure, grab/depth, returning to the dock, silence while Off and a
normal reboot. Do not describe simulated recovery tests as physical power-loss or
fresh-hardware testing.

Repeatable checks: `python3 -m unittest discover -s tests -v`,
`bash tools/test_storefront.sh`, `bash tools/test_dashboard.sh`, and
`python3 tools/test_update_lifecycle.py --live` on a Frame with SteamVR running.
The lifecycle probe uses an isolated disposable creation and real systemd/readiness
RPC, with local package transfers. It leaves the user's collection alone.
