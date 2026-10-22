#!/usr/bin/env python3
"""Opt-in Steam Frame lifecycle check using an isolated, disposable creation.

Uses real systemd services and readiness RPC. Package transfers use local fixtures.
Does not load an overlay, alter the user's collection, or restart SteamVR.
"""
import hashlib
import json
from pathlib import Path
import shutil
import socketserver
import sys
import tempfile
import threading
import uuid
import zipfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from magicshelf.contracts import machine
from magicshelf.manager import Manager, System
from magicshelf.server import LocalServer, response


def main():
    if sys.argv[1:] != ['--live']:
        raise SystemExit('Use --live on a Steam Frame with SteamVR running.')
    system = System()
    if not system.active('steamvr.service'):
        raise SystemExit('Start SteamVR before running this check.')
    key = 'org.magicshelf.update-check-' + uuid.uuid4().hex[:10]
    unit = 'magicshelf-module-' + key + '.service'
    unit_path = Path.home()/'.config/systemd/user'/unit
    assert not unit_path.exists()
    with tempfile.TemporaryDirectory(prefix='ms-updates-') as temp:
        root = Path(temp)
        manager = Manager(root/'home', root/'run', system)
        manager.units = unit_path.parent
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                packet = json.loads(self.rfile.readline(65536))
                self.wfile.write(json.dumps(response(manager, packet)).encode()+b'\n')
        server = LocalServer(str(manager.runtime/'manager.sock'), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        archives, transfers = {}, []
        def release(ver, broken=False):
            item = dict(schema_version=1, api_version=1, id=key, version=ver, name='Disposable update check',
                        description='Isolated lifecycle validation', author='MagicShelf', license='MIT', platform='linux',
                        architecture=machine(), entrypoint='bin/check', permissions=['vr-overlay'], memory_mb=64)
            script = '''#!/usr/bin/python3
import json, os, pathlib, socket, time
data=pathlib.Path(os.environ['MAGICSHELF_DATA_DIR'])
if not (data/'save').exists(): (data/'save').write_text('saved before update')
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
s.connect(os.environ['MAGICSHELF_RUNTIME_DIR']+'/manager.sock')
s.sendall((json.dumps({'api_version':1,'method':'runtime.ready','params':{'id':os.environ['MAGICSHELF_MODULE_ID'],'token':os.environ['MAGICSHELF_SESSION']}})+'\\n').encode())
s.recv(4096);s.close()
while True: time.sleep(1)
'''
            if broken:
                script = '#!/usr/bin/python3\nraise SystemExit(3)\n'
            archive = root/(ver+'.magicshelf')
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('module.json', json.dumps(item))
                info = zipfile.ZipInfo('bin/check'); info.external_attr = 0o100755 << 16
                z.writestr(info, script)
            item.update(catalog_url='https://github.com/josethevrtech/magicshelf',
                        url='https://github.com/josethevrtech/magicshelf/fixture/'+ver,
                        sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), size_bytes=archive.stat().st_size)
            archives[item['url']] = archive
            manager.state['catalog'] = [item]
        def transfer(url, path, limit, progress=None):
            transfers.append(url)
            if progress: progress(0)
            shutil.copy2(archives[url], path)
            if progress: progress(path.stat().st_size)
        def pid():
            return system.call('show', unit, '-p', 'MainPID', '--value').stdout.strip()
        try:
            with patch('magicshelf.manager.download', side_effect=transfer):
                release('1.0.0')
                manager.subscribe(key, True, ['vr-overlay'])
                manager.toggle(key, True)
                first_pid = pid()
                release('1.1.0')
                manager.sync_subscriptions(refresh=False)
                assert pid() == first_pid and first_pid != '0'
                assert manager.state['modules'][key]['version'] == '1.0.0'
                count = len(transfers)
                manager.sync_subscriptions(refresh=False)
                assert len(transfers) == count
                manager.toggle(key, False)
                assert len(transfers) == count
                assert manager.state['modules'][key]['version'] == '1.1.0'
                assert not system.active(unit)
                manager.toggle(key, True)
                assert system.active(unit)
                manager.toggle(key, False)
                release('1.2.0', broken=True)
                manager.sync_subscriptions(refresh=False)
                result = manager.toggle(key, True)
                assert manager.state['modules'][key]['version'] == '1.1.0'
                assert manager.state['modules'][key]['enabled'] and system.active(unit)
                assert 'previous version is running' in result['message']
                assert (manager.root/'module-data'/key/'save').read_text() == 'saved before update'
                count = len(transfers)
                manager.sync_subscriptions(refresh=False, manual=True)
                assert len(transfers) == count
                print(json.dumps({'running_update_kept_pid': True, 'cached_install_after_off': True,
                                  'bad_first_start_restored_working_version': True, 'saves_preserved': True,
                                  'bad_update_not_repeated': True}), flush=True)
        finally:
            system.call('disable', '--now', unit, check=False)
            unit_path.unlink(missing_ok=True)
            system.call('daemon-reload')
            server.shutdown(); server.server_close(); thread.join(5)


if __name__ == '__main__':
    main()
