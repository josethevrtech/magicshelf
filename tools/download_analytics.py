#!/usr/bin/env python3
"""Publisher report from GitHub counters. Never runs in the installed app."""
import argparse
import datetime as dt
import json
from pathlib import Path
import re
import urllib.request

REPOSITORIES = ['josethevrtech/magicshelf', 'josethevrtech/magicshelf-android-phone',
                'josethevrtech/magicshelf-smartphone-digivice', 'josethevrtech/magicshelf-pocket-pikachu']


def github(url):
    request = urllib.request.Request(url, headers={'Accept':'application/vnd.github+json',
                                                  'User-Agent':'MagicShelf-publisher-download-report',
                                                  'X-GitHub-Api-Version':'2022-11-28'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def collect(repository, fetch=github):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Expected a GitHub owner/repository')
    versions = []
    for page in range(1, 101):
        releases = fetch(f'https://api.github.com/repos/{repository}/releases?per_page=100&page={page}')
        if not isinstance(releases, list):
            raise ValueError('GitHub did not return release data')
        for release in releases:
            if release.get('draft'):
                continue
            packages = []
            installer = 0
            for asset in release.get('assets', []):
                name = asset['name']
                count = asset['download_count']
                if type(count) is not int or count < 0:
                    raise ValueError('Invalid GitHub download counter')
                if name.endswith('.magicshelf') or (name.startswith('magicshelf-') and name.endswith('.tar.gz')):
                    packages.append(dict(id=asset['id'], name=name, downloads=count, size_bytes=asset['size']))
                elif name == 'Install.MagicShelf.desktop':
                    installer += count
            if packages:
                versions.append(dict(version=release['tag_name'], published_at=release['published_at'],
                                     prerelease=bool(release.get('prerelease')), assets=packages,
                                     package_downloads=sum(a['downloads'] for a in packages),
                                     installer_downloads=installer))
        if len(releases) < 100:
            break
    else:
        raise RuntimeError('Release pagination limit reached; report not saved')
    versions.sort(key=lambda r:r['published_at'] or '', reverse=True)
    return dict(repository=repository, package_downloads=sum(r['package_downloads'] for r in versions),
                installer_downloads=sum(r['installer_downloads'] for r in versions), releases=versions)


def asset_counts(snapshot):
    return {str(a['id']):a['downloads'] for project in snapshot['projects']
            for release in project['releases'] for a in release['assets']}


def report(snapshot, previous=None):
    before = asset_counts(previous) if previous else None
    rows = ['# MagicShelf download statistics', '', 'Snapshot: '+snapshot['collected_at'], '',
            '**Source: GitHub release-asset download counters.** No analytics code runs on user devices.', '',
            'These are package fetches, not unique people, installs, active users or playtime. Updates, retries, reinstalls and developer/test downloads count too. Catalog polls, checksums, screenshots and launchers are excluded from package totals. Published prereleases are included and marked below.', '',
            '| Project | All package downloads | Latest published package | Latest downloads | Since previous snapshot |',
            '| --- | ---: | --- | ---: | ---: |']
    for project in sorted(snapshot['projects'], key=lambda p:p['package_downloads'], reverse=True):
        latest = project['releases'][0] if project['releases'] else None
        delta = None if before is None else sum(max(0,a['downloads']-before.get(str(a['id']),0))
                 for release in project['releases'] for a in release['assets'])
        rows.append('| '+project['repository'].split('/')[1]+' | '+str(project['package_downloads'])+' | '+
                    (latest['version'] if latest else 'None')+' | '+str(latest['package_downloads'] if latest else 0)+' | '+
                    (str(delta) if delta is not None else 'Baseline')+' |')
    if previous:
        removed = set(before)-set(asset_counts(snapshot))
        rows += ['', 'Comparison baseline: '+previous['collected_at']+'. '+str(len(removed))+' previously observed asset(s) no longer appear. New assets contribute their current counts; deleted assets and reset counters limit historical comparisons.']
    rows += ['', 'Download totals are a rough interest signal. Older releases have had more time to accumulate downloads, and frequent updates can increase totals without increasing the number of users.']
    for project in snapshot['projects']:
        rows += ['', '## '+project['repository'], '', '| Release | Published (UTC) | Package downloads |', '| --- | --- | ---: |']
        for release in project['releases']:
            rows.append('| '+release['version']+(' (prerelease)' if release['prerelease'] else '')+' | '+
                        str(release['published_at'])+' | '+str(release['package_downloads'])+' |')
        if project['installer_downloads']:
            rows += ['', 'Installer launcher downloads, counted separately: '+str(project['installer_downloads'])+'.']
    return '\n'.join(rows)+'\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('outputs/analytics'))
    args=parser.parse_args()
    # Fetch everything before writing: failed API calls never become zero counts.
    snapshot=dict(schema_version=1,collected_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                  source='GitHub public release asset counters', projects=[collect(repo) for repo in REPOSITORIES])
    directory=args.output;directory.mkdir(parents=True,exist_ok=True)
    previous=json.loads((directory/'latest.json').read_text()) if (directory/'latest.json').is_file() else None
    text=report(snapshot,previous)
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    data=json.dumps(snapshot,indent=2)+'\n'
    (directory/(stamp+'.json')).write_text(data,encoding='utf-8')
    (directory/'latest.next').write_text(data,encoding='utf-8');(directory/'latest.next').replace(directory/'latest.json')
    (directory/'report.md').write_text(text,encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
