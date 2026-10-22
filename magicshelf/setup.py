"""Creation-owned Steam prerequisites, presented without terminal commands."""
import re
import subprocess
import json
import os
import threading
import time
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
        ready, received, total, staged = False, 0, 0, 0
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
                staged = max(staged, int(fields.get('BytesStaged', '0')))
            except (OSError, ValueError):
                pass
        steps.append({'appid': item['appid'], 'title': item['title'], 'ready': bool(ready),
                      'received_bytes': received, 'total_bytes': total, 'staged_bytes': staged})
    missing = [s for s in steps if not s['ready']]
    return {'ready': not missing, 'steps': steps, 'remaining': len(missing),
            'message': 'Ready to use.' if not missing else 'Getting everything ready.'}


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


def request_download(home, appid):
    """Use the running Steam client; no terminal window or installation dialog."""
    require(type(appid) is int and 0 < appid <= 100000000, 'Invalid setup requirement.')
    try:
        pid = int((home/'.steam/steam.pid').read_text().strip())
        require(pid > 0, 'Open Steam, then retry setup.')
        os.kill(pid, 0)
    except (OSError, ValueError):
        raise ValueError('Open Steam, then retry setup.') from None
    # Steam handles entitlement and downloads. A successful command is only a
    # request: prepare() must observe installed files before reporting success.
    subprocess.run(['steam', '-ifrunning', '-silent', '+app_license_request', str(appid)],
                   check=True, timeout=15, capture_output=True)
    subprocess.run(['steam', '-ifrunning', '-silent', '+app_install', str(appid)],
                   check=True, timeout=15, capture_output=True)


def prepare(meta, home, wanted=lambda: True):
    for requirement in meta.get('steam_requirements', []):
        appid = requirement['appid']
        def current():
            return next(s for s in status(meta, home)['steps'] if s['appid'] == appid)
        if not wanted(): return
        if current()['ready']: continue
        request_download(home, appid)
        last_progress, last_change, retry_at = None, time.monotonic(), time.monotonic() + 5
        while wanted():
            step = current()
            if step['ready']: break
            progress = (step['received_bytes'], step['total_bytes'], step['staged_bytes'])
            now = time.monotonic()
            if progress != last_progress:
                last_progress, last_change = progress, now
            # Entitlement requests can finish after app_install is dispatched.
            if retry_at and now >= retry_at:
                retry_at = None
                if not step['total_bytes']:
                    request_download(home, appid)
            if now - last_change >= 180:
                raise ValueError('Setup paused. Check Wi-Fi or try again.')
            time.sleep(1)
        else:
            return


class AutomaticSetup:
    """Persistent, nonblocking setup jobs. Only approved installed creations run."""
    def __init__(self, manager):
        self.manager = manager
        self.path = manager.config/'creation-setup.json'
        self.lock = threading.RLock()
        self.thread = None
        try:
            self.jobs = json.loads(self.path.read_text())
            if not isinstance(self.jobs, dict) or any(
                not isinstance(j, dict) or not isinstance(j.get('version'), str)
                or j.get('stage') not in ('queued', 'running', 'failed')
                or type(j.get('attempts')) is not int
                or not isinstance(j.get('retry_at'), (int, float))
                for j in self.jobs.values()
            ):
                self.jobs = {}
        except (OSError, ValueError):
            self.jobs = {}
        for job in self.jobs.values():
            if job['stage'] == 'running':
                job.update(stage='queued', retry_at=0)

    def save(self):
        from .manager import atomic
        atomic(self.path, self.jobs)

    def valid(self, key, version):
        return self.manager.state['modules'].get(key, {}).get('version') == version

    def queue(self, key, retry=False):
        m = self.manager
        require(key in m.state['modules'] and not m.is_adapter(key), 'Download this creation first.')
        meta = m.metadata(key, m.state['modules'][key])
        if status(meta, m.home)['ready']: return
        with self.lock:
            old = self.jobs.get(key, {})
            if old.get('version') == meta['version'] and (old.get('stage') in ('running', 'queued') or not retry):
                return
            self.jobs[key] = {'version': meta['version'], 'stage': 'queued', 'attempts': 0, 'retry_at': 0, 'error': ''}
            self.save()

    def snapshot(self, meta):
        result = status(meta, self.manager.home)
        with self.lock:
            job = dict(self.jobs.get(meta['id'], {}))
        stage = job.get('stage', 'idle') if job.get('version') == meta['version'] else 'idle'
        result.update(stage='ready' if result['ready'] else stage, error=job.get('error', ''))
        return result

    def tick(self):
        m = self.manager
        if m.busy or m.framework.snapshot().get('stage') == 'installing': return
        with self.lock:
            if self.thread and self.thread.is_alive(): return
            stale = [k for k,j in self.jobs.items() if not self.valid(k,j['version'])]
            for key in stale: del self.jobs[key]
            if stale: self.save()
            for key, job in self.jobs.items():
                if job['stage'] == 'queued' or (job['stage'] == 'failed' and job['attempts'] < 3 and time.time() >= job['retry_at']):
                    self.thread = threading.Thread(target=self.run, args=(key, job['version']), daemon=True)
                    self.thread.start()
                    break

    def run(self, key, version):
        with self.lock:
            job = self.jobs.get(key, {})
            if job.get('version') != version or not self.valid(key, version): return
            job.update(stage='running', attempts=job['attempts']+1, error='')
            self.save()
        try:
            m = self.manager
            meta = m.metadata(key, {'version': version})
            prepare(meta, m.home, lambda: self.valid(key, version))
            with self.lock:
                if self.jobs.get(key, {}).get('version') == version:
                    del self.jobs[key]
                    self.save()
        except Exception as error:
            with self.lock:
                if self.jobs.get(key, {}).get('version') == version:
                    message = str(error) if isinstance(error, ValueError) else 'Steam could not finish setup. Try again.'
                    job.update(stage='failed', error=message[:180], retry_at=time.time()+60*job['attempts'])
                    self.save()
        finally:
            self.manager.publish()
