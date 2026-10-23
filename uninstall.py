#!/usr/bin/env python3
"""Remove per-user integration, including partially removed installations."""
import argparse
import contextlib
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

OWNED_UNIT = re.compile(r'magicshelf(?:-vr|-update|-module-[A-Za-z0-9_.-]+)?\.service')


def desktop_directory(home):
    try:
        result = subprocess.run(['xdg-user-dir', 'DESKTOP'], capture_output=True, text=True, timeout=5)
        path = Path(result.stdout.strip())
        if result.returncode == 0 and path.is_absolute() and path.is_relative_to(home):
            return path
    except (OSError, subprocess.SubprocessError):
        pass
    return home/'Desktop'


def system(*args, check=True):
    result = subprocess.run(['systemctl', '--user', *args], capture_output=True, text=True, timeout=90)
    if result.stdout: print(result.stdout.rstrip())
    if result.stderr: print(result.stderr.rstrip(), file=sys.stderr)
    if check and result.returncode:
        raise RuntimeError('MagicShelf could not finish stopping. Please try again. Your saved data is safe.')
    return result


def properties(unit):
    result = system('show', unit, '-p', 'LoadState', '-p', 'ActiveState', '-p', 'MainPID', check=False)
    values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    if not all(key in values for key in ('LoadState', 'ActiveState', 'MainPID')):
        raise RuntimeError('Could not reach your desktop session. Open Uninstall MagicShelf from your desktop, without sudo.')
    return values


def stop(unit):
    before = properties(unit)
    if before['LoadState'] != 'not-found' or before['ActiveState'] != 'inactive':
        system('stop', unit)
    after = properties(unit)
    if after['ActiveState'] not in ('inactive', 'failed') or after['MainPID'] != '0':
        raise RuntimeError('MagicShelf is still running. Nothing has been removed. Please try again.')


def uninstall(progress=lambda label: None):
    if os.geteuid() == 0:
        raise RuntimeError('Open Uninstall MagicShelf from your own desktop. No administrator password is needed.')
    home = Path.home()
    root = home/'.local/share/magicshelf'
    config = home/'.config/magicshelf'
    units = home/'.config/systemd/user'
    root.mkdir(parents=True, exist_ok=True)
    with (root/'install.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('MagicShelf is finishing an update. Try uninstalling again in a moment.') from None
        # Check the session before changing anything. Keep this marker until an
        # explicit install so a delayed update cannot bring the app back.
        properties('magicshelf.service')
        (root/'uninstalled').touch()
        progress('Stopping MagicShelf…')
        stop('magicshelf.service')
        stop('magicshelf-update.service')
        stop('magicshelf-vr.service')
        # A failed older uninstall may delete unit files while processes remain.
        listed = system('list-units', '--all', '--plain', '--no-legend', 'magicshelf*.service')
        names = {'magicshelf.service', 'magicshelf-vr.service', 'magicshelf-update.service'}
        names.update(line.split()[0] for line in listed.stdout.splitlines() if line.split() and OWNED_UNIT.fullmatch(line.split()[0]))
        names.update(p.name for p in units.glob('magicshelf*.service') if OWNED_UNIT.fullmatch(p.name))
        for path in units.glob('*.wants/magicshelf*.service'):
            if OWNED_UNIT.fullmatch(path.name): names.add(path.name)
        for name in sorted(names): stop(name)
        progress('Removing shortcuts…')
        binary = root/'current/bin/magicshelf-vr'
        if binary.is_file() and properties('steamvr.service')['ActiveState'] == 'active':
            result = subprocess.run([str(binary), '--unregister'], capture_output=True, text=True, timeout=20)
            print(result.stdout + result.stderr)
            if result.returncode:
                raise RuntimeError('MagicShelf stopped, but its SteamVR shortcut could not be removed. Please try again.')
        # Missing unit files are normal on repeated removal. Remove only owned
        # links instead of asking disable --now to operate on missing units.
        for name in sorted(names):
            (units/name).unlink(missing_ok=True)
            for link in units.glob('*.wants/'+name): link.unlink(missing_ok=True)
            for link in units.glob('*.requires/'+name): link.unlink(missing_ok=True)
        for name in ('android-phone-vr.service', 'digitalpartner-vr.service'):
            (units/(name+'.d')/'magicshelf.conf').unlink(missing_ok=True)
        system('daemon-reload')
        for name in sorted(names):
            values = properties(name)
            if values['ActiveState'] == 'failed': system('reset-failed', name)
            if values['ActiveState'] not in ('inactive', 'failed') or values['MainPID'] != '0':
                raise RuntimeError('MagicShelf is still running. Please try uninstalling again.')
        (config/'magicshelf.vrmanifest').unlink(missing_ok=True)
        (root/'framework-install.json').unlink(missing_ok=True)
        (config/'framework-update.json').unlink(missing_ok=True)
        # Saved creations remain available, but stay Off after a reinstall.
        statepath = config/'state.json'
        if statepath.exists():
            try:
                state = json.loads(statepath.read_text())
                for item in state['modules'].values(): item['enabled'] = False
                temporary = statepath.with_suffix('.next')
                temporary.write_text(json.dumps(state, indent=2)+'\n')
                temporary.chmod(0o600); os.replace(temporary, statepath)
            except (ValueError, KeyError, TypeError, AttributeError):
                print('Saved settings could not be read; the original file was kept.')
        for name in ('com.josethevrtech.magicshelf.desktop', 'com.josethevrtech.magicshelf.uninstall.desktop'):
            (home/'.local/share/applications'/name).unlink(missing_ok=True)
        desktop = desktop_directory(home)
        for name in ('MagicShelf.desktop', 'Uninstall MagicShelf.desktop'):
            (desktop/name).unlink(missing_ok=True)
        print('MagicShelf is uninstalled. Your creations and saved data are kept. Use Install MagicShelf to install again.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gui', action='store_true')
    args = parser.parse_args(argv)
    gui = args.gui and shutil.which('kdialog')
    if args.gui and not gui:
        print('Could not open the uninstall dialog. Run this from Desktop Mode.', file=sys.stderr)
        return 1
    if gui:
        choice = subprocess.run(['kdialog', '--title', 'Uninstall MagicShelf', '--yes-label', 'Uninstall', '--no-label', 'Cancel', '--warningyesno', 'Uninstall MagicShelf? Your creations and saved data will be kept.'])
        if choice.returncode: return 0
    log = Path.home()/'.local/state/magicshelf/uninstall.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    ref = []; dbus = shutil.which('qdbus6') or shutil.which('qdbus')
    def progress(label):
        if ref:
            with contextlib.suppress(OSError, subprocess.SubprocessError):
                subprocess.run([dbus, *ref, 'setLabelText', label], capture_output=True, timeout=3)
    error = None
    try:
        if gui and dbus:
            result = subprocess.run(['kdialog', '--title', 'MagicShelf', '--progressbar', 'Stopping MagicShelf…', '0'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0: ref = result.stdout.split()
        with log.open('w') as stream, contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            log.chmod(0o600)
            uninstall(progress)
    except Exception as exception:
        error = str(exception)
        with log.open('a') as stream: stream.write('\n'+error+'\n')
    finally:
        if ref:
            with contextlib.suppress(OSError, subprocess.SubprocessError):
                subprocess.run([dbus, *ref, 'close'], capture_output=True, timeout=3)
    message = error or 'MagicShelf is uninstalled. Your creations and saved data are kept. You can use Install MagicShelf again anytime.'
    if gui:
        subprocess.run(['kdialog', '--title', 'MagicShelf', '--error' if error else '--msgbox', message])
    else: print(message, file=sys.stderr if error else sys.stdout)
    return 1 if error else 0


if __name__ == '__main__': sys.exit(main())
