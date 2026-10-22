"""Creation-owned Steam prerequisites, presented without terminal commands."""
import re
import subprocess
from pathlib import Path

from .contracts import require


def steam_roots(home):
    roots = [home/'.local/share/Steam', home/'.steam/steam']
    for base in list(roots):
        path = base/'steamapps/libraryfolders.vdf'
        if path.is_file():
            for folder in re.findall(r'"path"\s+"([^"]+)"', path.read_text()):
                candidate = Path(folder.replace('\\\\', '\\'))
                if candidate.is_absolute():
                    roots.append(candidate)
    return list(dict.fromkeys(p.resolve() for p in roots))


def status(meta, home):
    steps = []
    for item in meta.get('steam_requirements', []):
        ready, received, total = False, 0, 0
        for root in steam_roots(home):
            path = root/'steamapps'/('appmanifest_'+str(item['appid'])+'.acf')
            try:
                fields = dict(re.findall(r'"([A-Za-z]+)"\s+"([^"\n]*)"', path.read_text()))
                installed = int(fields.get('StateFlags', '0')) & 4 and not int(fields.get('StateFlags', '0')) & (2 | 1024)
                if installed and all((root/'steamapps/common'/name).is_file() for name in item['files']):
                    ready = True
                    break
                received = max(received, int(fields.get('BytesDownloaded', '0')))
                total = max(total, int(fields.get('BytesToDownload', '0')))
            except (OSError, ValueError):
                pass
        steps.append({'appid': item['appid'], 'title': item['title'], 'ready': bool(ready),
                      'received_bytes': received, 'total_bytes': total})
    missing = [s for s in steps if not s['ready']]
    return {'ready': not missing, 'steps': steps, 'remaining': len(missing),
            'message': 'Ready to use.' if not missing else 'One quick setup before you begin. Steam will handle the downloads.'}


def locations(meta, home):
    result = {}
    for item in meta.get('steam_requirements', []):
        for root in steam_roots(home):
            if all((root/'steamapps/common'/name).is_file() for name in item['files']):
                result[item['appid']] = root/'steamapps/common'/Path(item['files'][0]).parts[0]
                break
    return result


def open_step(meta, home, appid):
    require(type(appid) is int, 'Choose a setup step first.')
    current = status(meta, home)
    step = next((s for s in current['steps'] if s['appid'] == appid and not s['ready']), None)
    require(step is not None, 'That setup step is already finished. You can open your creation.')
    subprocess.run(['xdg-open', 'steam://install/'+str(step['appid'])], check=True, timeout=10, capture_output=True)
