#!/usr/bin/env python3
"""Remove MagicShelf integration while keeping downloaded code and all saved data."""
import json,subprocess
from pathlib import Path
home=Path.home();units=home/'.config/systemd/user';root=home/'.local/share/magicshelf'
def system(*args):subprocess.run(['systemctl','--user',*args],check=False)
statepath=home/'.config/magicshelf/state.json'
state=json.loads(statepath.read_text()) if statepath.exists() else {'modules':{}}
for key,item in state['modules'].items():
    if not item.get('adapter'):
        unit='magicshelf-module-'+key+'.service';system('disable','--now',unit);(units/unit).unlink(missing_ok=True)
system('disable','--now','magicshelf-vr.service','magicshelf.service')
subprocess.run([str(root/'current/bin/magicshelf-vr'),'--unregister'],check=False)
for name in ['magicshelf-vr.service','magicshelf.service']:(units/name).unlink(missing_ok=True)
for name in ['android-phone-vr.service','digitalpartner-vr.service']:
    (units/(name+'.d')/'magicshelf.conf').unlink(missing_ok=True)
system('daemon-reload')
for name in ['android-phone-vr.service','digitalpartner-vr.service']:
    if subprocess.run(['systemctl','--user','is-active','--quiet',name]).returncode==0:system('restart',name)
(home/'.local/share/applications/com.josethevrtech.magicshelf.desktop').unlink(missing_ok=True)
(home/'Desktop/MagicShelf.desktop').unlink(missing_ok=True)
print('MagicShelf integration removed. All saved data and releases are kept in ~/.local/share/magicshelf and ~/.config/magicshelf.')
