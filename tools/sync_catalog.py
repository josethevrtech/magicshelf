#!/usr/bin/env python3
"""Mirror registered creation catalogs for older MagicShelf installations."""
import json
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from magicshelf.collections import catalogs
from magicshelf.contracts import catalog, load
from magicshelf.packages import download


def sync(root=ROOT):
    urls = catalogs(load(root / 'collections.json'))
    previous = catalog(load(root / 'catalog.json'))['modules']
    def fetch(url):
        try:
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / 'catalog.json'
                download(url, path, 1024 * 1024)
                return catalog(load(path))['modules'], None
        except Exception as error:
            return [m for m in previous if m.get('collection_url') == url], str(error)
    items, seen, failures = [], set(), []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for url, (entries, error) in zip(urls, pool.map(fetch, urls)):
            if error:
                failures.append(url)
                print('Keeping cached collection: ' + url, file=sys.stderr)
            for item in entries:
                key = (item['id'], item['architecture'])
                if key in seen:
                    raise ValueError('Duplicate creation in registered collections: ' + item['id'])
                seen.add(key)
                items.append({**item, 'collection_url': url})
    # A complete outage must not replace the directory with an empty listing.
    if urls and len(failures) == len(urls):
        raise RuntimeError('Collections are offline; existing catalog kept')
    value = catalog({'schema_version': 1, 'name': 'MagicShelf', 'modules': items})
    (root / 'catalog.json').write_text(json.dumps(value, indent=2) + '\n')
    return value


if __name__ == '__main__':
    sync()
