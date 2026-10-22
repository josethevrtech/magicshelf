# Exclusive testing readiness

Status on October 21, 2026: MagicShelf 0.3.7 is installed and validated on the
development Steam Frame. It is not yet a fresh-device tester release. The public
framework installer still downloads 0.1.3. Independent creations require the newer
framework, and reinstalling them on the development Frame reused existing inputs.

## Verified update behavior

- Catalog checks run after startup and every five minutes. Manual checks return
  immediately. An unavailable publisher does not prevent healthy catalogs updating.
- A subscribed creation keeps running while its update downloads. Turning it Off
  installs the verified cached archive. An already Off creation updates directly.
- Transient downloads retry, incomplete files are discarded, and failures leave
  the installed version in place. New permissions require review.
- Interrupted creation installs and restores recover from a journal. A failed
  first start after an update installed while Off restores the previous version.
- Restore previous holds the replaced release until explicit approval or a newer
  release. Unsubscribing cancels pending installation. Saved module data is kept.

These checks cover creation updates. There is no automatic updater for the
MagicShelf framework itself yet. Recovery backups cover `module-data`; external
runtime data is owned by each creation and needs separate validation.

## Required before inviting fresh-device testers

1. Publish a compatible framework release and update its installer link only after
   downloading and running the public artifact on a fresh supported device. The
   existing 0.1.3 link does not install the current storefront/SDK.
2. Give the framework a straightforward upgrade path for testers, with a clear
   version, progress, failure recovery and a way to retry. Creation subscriptions
   alone do not upgrade MagicShelf.
3. Complete first-run setup for Android Phone (Virtual). Its runtime currently
   requires Steam's Lepton installation and prepares a private copy of supported
   runtime files. Check missing and changed Lepton versions on a fresh Frame.
4. Complete first-run setup for Smartphone Digivice. Its runtime currently expects
   separately imported game and model inputs under `creation-inputs`, plus Steam
   ARM64 Proton and Steam Linux Runtime. A fresh subscription cannot supply those
   inputs. Provide a supported package or clear guided setup and an actionable
   missing-input screen before offering it to nontechnical testers.
5. Test the public install, subscription, first launch and one real update using a
   fresh user/device without the developer's accounts, inputs or cached runtime.
   Confirm Configure, grab/depth, dock recovery and silence when Off, then repeat
   after a normal device reboot. Reinstalling on the prepared development Frame
   is not evidence of a successful fresh-device experience.

## Repeatable validation

Run `python3 -m unittest discover -s tests -v`, `bash tools/test_storefront.sh`
and `bash tools/test_dashboard.sh`. Build on the advertised architecture.

On a Frame with SteamVR running, run
`python3 tools/test_update_lifecycle.py --live`. This creates and cleans up a
disposable systemd creation, uses real readiness RPC, and verifies an active
process survives background download, cached installation occurs after Off, and a
bad first launch restores the working version and its saved module data. Transfers
use local fixture packages; this does not replace a public download or fresh-device
test. It does not load an overlay or change the user's collection.

Detailed results are recorded in [VALIDATION.md](VALIDATION.md).
