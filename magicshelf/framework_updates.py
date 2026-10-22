"""Verified framework downloads; installation runs outside the app's service."""
import hashlib
import re
import shutil
import subprocess
import tarfile
import tempfile
import threading
import time
from pathlib import Path, PurePosixPath

from . import VERSION
from .contracts import load, machine, require, version
from .packages import download
from .updates import update_error

OFFICIAL_RELEASES = 'https://github.com/josethevrtech/magicshelf/releases/'
UPDATE_URL = OFFICIAL_RELEASES + 'latest/download/framework.json'
MAX_FRAMEWORK = 100 * 1024 * 1024


def release_for(data, architecture):
    require(isinstance(data, dict) and data.get('schema_version') == 1, 'The update information could not be read. Try again later.')
    version(data.get('version'))
    require(isinstance(data.get('artifacts'), dict), 'The update is not ready for this device yet.')
    item = data['artifacts'].get(architecture)
    require(isinstance(item, dict), 'The update is not ready for this device yet.')
    expected = OFFICIAL_RELEASES + f'download/v{data["version"]}/magicshelf-{data["version"]}-linux-{architecture}.tar.gz'
    require(item.get('url') == expected, 'This update is not an official MagicShelf download.')
    require(isinstance(item.get('sha256'), str) and re.fullmatch('[a-f0-9]{64}', item['sha256']), 'The update verification details are missing.')
    require(type(item.get('size_bytes')) is int and 0 < item['size_bytes'] <= MAX_FRAMEWORK, 'The update size is invalid.')
    return {'url': item['url'], 'sha256': item['sha256'], 'size_bytes': item['size_bytes'], 'version': data['version'], 'architecture': architecture}


def extract_release(archive, destination, item):
    require(archive.stat().st_size == item['size_bytes'], 'The download did not finish. Please try again.')
    with archive.open('rb') as stream:
        require(hashlib.file_digest(stream, 'sha256').hexdigest() == item['sha256'], 'The download could not be verified. Please try again.')
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        require(len(members) <= 8192 and sum(m.size for m in members) <= MAX_FRAMEWORK * 4, 'The update could not be verified.')
        seen = set()
        for m in members:
            path = PurePosixPath(m.name)
            require(not path.is_absolute() and '..' not in path.parts and path.parts and path.parts[0] == 'magicshelf' and (m.isfile() or m.isdir()), 'The update could not be verified.')
            require(m.name not in seen, 'The update contains duplicate files.')
            seen.add(m.name)
        tar.extractall(destination, filter='data')
    source = destination/'magicshelf'
    info = load(source/'release.json')
    require(info['version'] == item['version'] and info['architecture'] == item['architecture'], 'This update does not match your device.')
    require(isinstance(info.get('files'), dict) and 'install.py' in info['files'], 'The update is incomplete.')
    for name, digest in info['files'].items():
        from .contracts import relative
        relative(name)
        path = source/name
        require(path.is_file() and not path.is_symlink(), 'The update is incomplete.')
        with path.open('rb') as stream:
            require(hashlib.file_digest(stream, 'sha256').hexdigest() == digest, 'The update could not be verified.')
    return source


class FrameworkUpdates:
    def __init__(self, manager):
        self.manager = manager
        self.path = manager.config/'framework-update.json'
        self.root = manager.root/'framework-downloads'
        self.lock = threading.Lock()

    def snapshot(self):
        try:
            data = load(self.path)
            require(isinstance(data, dict) and data.get('stage') in ('idle','current','downloading','ready','failed','installing'), 'Invalid update state')
            version(data.get('version', VERSION))
            return data
        except (OSError, ValueError):
            return {'stage': 'idle', 'version': VERSION, 'message': 'MagicShelf checks for updates automatically.'}

    def set(self, **state):
        from .manager import atomic
        atomic(self.path, state)
        self.manager.publish()

    def check(self):
        if not self.lock.acquire(blocking=False):
            return
        try:
            previous = self.snapshot()
            if previous.get('stage') == 'installing':
                return
            self.root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=self.root) as tmp:
                tmp = Path(tmp)
                download(UPDATE_URL, tmp/'framework.json', 65536)
                item = release_for(load(tmp/'framework.json'), machine())
                if version(item['version']) <= version(VERSION):
                    self.set(stage='current', version=VERSION, message='MagicShelf is up to date.')
                    return
                target = self.root/item['version']
                if previous.get('stage') == 'ready' and previous.get('sha256') == item['sha256'] and (target/'magicshelf/release.json').is_file() and (target/'update.tar.gz').is_file():
                    return
                self.set(stage='downloading', message='Downloading the MagicShelf update. Keep using your shelf.', received_bytes=0, total_bytes=item['size_bytes'], **item)
                last_publish = 0.
                def progress(received):
                    nonlocal last_publish
                    now = time.monotonic()
                    if now - last_publish < .2 and received != item["size_bytes"]:
                        return
                    last_publish = now
                    self.set(stage='downloading', message='Downloading the MagicShelf update. Keep using your shelf.', received_bytes=received, total_bytes=item['size_bytes'], **item)
                download(item['url'], tmp/'update.tar.gz', item['size_bytes'], progress=progress)
                extract_release(tmp/'update.tar.gz', tmp/'unpacked', item)
                if target.exists():
                    shutil.rmtree(target)
                (tmp/'unpacked').rename(target)
                shutil.move(tmp/'update.tar.gz', target/'update.tar.gz')
                self.set(stage='ready', message='A MagicShelf update is ready. Your creations will keep running.', **item)
        except Exception as error:
            # Keep a verified ready download usable during a temporary outage.
            if self.snapshot().get('stage') != 'ready':
                self.set(stage='failed', version=VERSION, message=update_error(error), retry=True)
        finally:
            self.lock.release()

    def spawn_worker(self, source):
        worker = Path(__file__).with_name('framework_worker.py')
        self.manager.system.call('reset-failed', 'magicshelf-update.service', check=False)
        subprocess.run(['systemd-run', '--user', '--collect', '--unit=magicshelf-update', '--property=Restart=on-failure', '--property=RestartSec=3',
                        '/usr/bin/python3', str(worker), str(source)], check=True, timeout=10, capture_output=True)

    def recover_after_restart(self):
        state = self.snapshot()
        if state.get('stage') != 'installing' or self.manager.system.active('magicshelf-update.service'):
            return
        try:
            if (self.manager.root/'framework-install.json').exists():
                self.spawn_worker(self.root/state['version']/'magicshelf')
            elif version(state['version']) <= version(VERSION):
                self.set(stage='current', version=VERSION, message='MagicShelf is up to date.')
            else:
                self.set(**{**state, 'stage': 'ready', 'message': 'The update was interrupted. Try Update and reopen when ready.'})
        except Exception:
            self.set(**{**state, 'stage': 'failed', 'message': 'The update was interrupted. Choose Check updates to try again.'})

    def install(self):
        manager = self.manager
        require(not manager.busy and not manager._sync_lock.locked(), 'Please let the current download finish, then try again.')
        with self.lock:
            state = self.snapshot()
            require(state.get('stage') == 'ready', 'Choose Check updates to get the latest MagicShelf update.')
            source = self.root/state['version']/'magicshelf'
            require(source.is_dir(), 'The update needs to download again. Choose Check updates.')
            self.set(**{**state, 'stage': 'installing', 'message': 'Updating MagicShelf. It will reopen automatically.'})
            try:
                self.spawn_worker(source)
            except Exception:
                self.set(**{**state, 'message': 'The update could not start. Please try Update and reopen again.'})
                raise
        return manager.snapshot()
