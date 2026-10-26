# Update notices and publisher download statistics

## What testers see in MagicShelf 0.3.21

When a subscribed creation is On, its update downloads and is verified without
restarting the creation. SteamVR receives one transient notice for that creation
and update version. It respects SteamVR's notification behavior rather than
using a forced system notification. The notice points to MagicShelf's Updates
ready page.

The page explicitly says that running creations are not restarted automatically:

- Later dismisses reminders for that update and leaves the creation running.
- Turning the creation Off applies the verified cached update automatically.
- Update now opens the existing confirmation explaining that it restarts an On
  creation and preserves its saved data. No installation starts before confirmation.

The notification marker is stored locally and survives manager/dashboard restarts.
A newer version gets a fresh notice. Withdrawn, failed, unverified and
permissions-blocked updates do not get a ready notification. If SteamVR's notice
service is unavailable, the Updates ready page and creation-card badges remain
available; failures do not stop creations.

## Explicit download-statistics disclosure

Settings > Credits and the diagnostic web view display:

> Download totals come from GitHub. Updates and repeat downloads count too.
> MagicShelf sends no playtime or device-usage analytics.

The release notes must state this as well so existing testers see the change.
No device identifiers, usage sessions, playtime events or tracking endpoints were
added to the installed app. Existing downloads still contact their publishers.

## Publisher report

GitHub already provides cumulative download_count on release assets:
https://docs.github.com/en/rest/releases/releases

Run `python3 tools/download_analytics.py --output outputs/analytics` from the
publisher's source checkout. The standard-library-only tool reads the four public
repositories, saves a timestamped JSON snapshot, and writes report.md plus
latest.json. Later refreshes compare counters with the previous local snapshot.
Counts continue accumulating at GitHub between report refreshes; local historical
snapshots are only recorded when the report runs.

Only .magicshelf packages and framework tarballs count toward package totals.
Catalog polling, checksums, screenshots and launcher downloads are excluded.
Installer launcher downloads are listed separately. Published prereleases are
included and marked. Both framework architectures count if present.

These counts cannot establish unique users, installs, retention or favorites.
Automatic updates, retries, reinstalls and developer/test downloads count too.
Older releases have had longer to accumulate downloads. Deleting release assets
or resetting counters limits historical comparisons. API errors stop collection
and retain the previous report; they never silently become zero downloads.

This publisher tool is not part of the runtime release allowlist and never runs
on testers' devices.
