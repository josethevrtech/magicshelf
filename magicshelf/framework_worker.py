"""Independent update worker, kept alive when MagicShelf restarts."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from magicshelf.manager import atomic
from magicshelf.contracts import load, require
from magicshelf.framework_updates import extract_release, release_for


def main(source):
    home = Path.home()
    root = home/'.local/share/magicshelf'
    if (root/'uninstalled').exists():
        return
    status = home/'.config/magicshelf/framework-update.json'
    current = root/'current'
    journal = root/'framework-install.json'
    require(source.resolve().parent.parent == (root/'framework-downloads').resolve(), 'Unexpected update location')
    state = load(status)
    if journal.exists():
        # A worker interruption leaves its original working release recorded.
        saved = load(journal)
        previous = Path(saved['previous'])
        require(previous.parent == root/'releases' and previous.is_dir(), 'Previous MagicShelf release is missing')
        link = root/'current.recovery'
        link.unlink(missing_ok=True);link.symlink_to(previous);os.replace(link, current)
        subprocess.run(['systemctl', '--user', 'restart', 'magicshelf.service', 'magicshelf-vr.service'], check=True, timeout=60)
        atomic(status, {**state, 'stage': 'ready', 'message': 'The update was interrupted. Your previous MagicShelf is restored. Try again when ready.'})
        journal.unlink()
        return
    atomic(journal, {'previous': str(current.resolve()), 'target': state['version']})
    try:
        item = release_for({'schema_version': 1, 'version': state['version'], 'artifacts': {state['architecture']: state}}, state['architecture'])
        with tempfile.TemporaryDirectory(dir=source.parent) as temp:
            verified = extract_release(source.parent/'update.tar.gz', Path(temp), item)
            spec = importlib.util.spec_from_file_location('framework_installer', verified/'install.py')
            installer = importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)
            installer.install(verified, automatic=True)
        atomic(status, {'stage': 'current', 'version': state['version'], 'message': 'MagicShelf is up to date.'})
        journal.unlink()
        if state.get('reopen', True):
            subprocess.run([str(current/'bin/magicshelf-vr'), '--show'], check=False, timeout=10, capture_output=True)
    except Exception:
        # install.py restores the previous release and services on failure.
        atomic(status, {**state, 'stage': 'ready', 'message': 'The update could not finish. Your previous MagicShelf is kept. Try again when ready.'})
        journal.unlink(missing_ok=True)


if __name__ == '__main__':
    main(Path(sys.argv[1]))
