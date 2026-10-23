#!/usr/bin/env python3
"""Build immutable framework assets and a pinned single-file launcher."""
import argparse, base64, hashlib, json, os, shutil, stat, tarfile, tempfile, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
VERSION='0.3.15'
REPO='josethevrtech/magicshelf'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def build(arch):
    out=ROOT/'dist';out.mkdir(exist_ok=True)
    # Creation packages and catalogs are released by their own repositories.
    shutil.copy2(ROOT/'catalog.json', out/'catalog.json')
    with tempfile.TemporaryDirectory() as temp:
        payload=Path(temp)/'magicshelf';payload.mkdir()
        for name in ['magicshelf','bin']:
            shutil.copytree(ROOT/name,payload/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        shutil.copy2(ROOT/'build/bin/magicshelf-vr',payload/'bin/magicshelf-vr')
        for name in ['collections.json','shelf.json','install.py','uninstall.py','LICENSE','OPENVR-LICENSE.txt','build/icon.png']:
            shutil.copy2(ROOT/name,payload/Path(name).name)
        (payload/'bundled').mkdir()
        shutil.copy2(out/'catalog.json',payload/'catalog.json')
        release={'schema_version':1,'version':VERSION,'api_version':1,'architecture':arch,'bundled':[]}
        for path in (payload/'bin').iterdir():path.chmod(0o755)
        release['files']={str(p.relative_to(payload)):sha(p) for p in sorted(payload.rglob('*')) if p.is_file()}
        (payload/'release.json').write_text(json.dumps(release,indent=2)+'\n')
        archive=out/f'magicshelf-{VERSION}-linux-{arch}.tar.gz'
        with tarfile.open(archive,'w:gz') as tar:tar.add(payload,arcname='magicshelf')
    # The reusable launcher pins this small bootstrap. It discovers and verifies
    # the latest archive each time, so a saved desktop icon never installs old code.
    bootstrap=out/'install-magicshelf.py'
    bootstrap.write_text((ROOT/'tools/bootstrap.py.in').read_text().replace('@ARCH@',arch))
    launcher_source="""import hashlib,pathlib,subprocess,tempfile,urllib.request
try:
    with tempfile.TemporaryDirectory(prefix='magicshelf-') as temp:
        path=pathlib.Path(temp)/'install.py'
        with urllib.request.urlopen('@BOOTSTRAP_URL@',timeout=45) as response:
            data=response.read(1048577)
        if len(data)>1048576 or hashlib.sha256(data).hexdigest()!='@BOOTSTRAP_SHA@':
            raise RuntimeError('The download could not be verified. Nothing was changed. Please try again.')
        path.write_bytes(data)
        raise SystemExit(subprocess.run(['python3',str(path)]).returncode)
except Exception as error:
    print('MagicShelf:',error)
    try:subprocess.run(['kdialog','--error',str(error)],check=False)
    except FileNotFoundError:pass
    raise SystemExit(1)
""".replace('@BOOTSTRAP_URL@',f'https://github.com/{REPO}/releases/download/v{VERSION}/install-magicshelf.py').replace('@BOOTSTRAP_SHA@',sha(bootstrap))
    # Base64 is just argument quoting for Desktop Entry's Exec grammar.
    code="import base64;exec(base64.b64decode('"+base64.b64encode(launcher_source.encode()).decode()+"'))"
    escaped=code.replace('\\','\\\\').replace('"','\\"').replace('%','%%')
    (out/'Install.MagicShelf.desktop').write_text('[Desktop Entry]\nType=Application\nName=Install MagicShelf\nComment=Install the MagicShelf shelf and module library\nExec=python3 -c "'+escaped+'"\nIcon=applications-games\nTerminal=false\nCategories=Game;\n')
    (out/'Install.MagicShelf.desktop').chmod(0o755)
    # Standalone recovery uninstaller also works after a partial old removal.
    uninstaller=out/'uninstall-magicshelf.py'
    shutil.copy2(ROOT/'uninstall.py',uninstaller)
    uninstall_source=launcher_source.replace('/install-magicshelf.py', '/uninstall-magicshelf.py').replace(sha(bootstrap),sha(uninstaller)).replace("str(path)]", "str(path),'--gui']")
    code="import base64;exec(base64.b64decode('"+base64.b64encode(uninstall_source.encode()).decode()+"'))"
    escaped=code.replace('\\','\\\\').replace('"','\\"').replace('%','%%')
    (out/'Uninstall.MagicShelf.desktop').write_text('[Desktop Entry]\nType=Application\nName=Uninstall MagicShelf\nComment=Remove MagicShelf and keep saved data\nExec=python3 -c "'+escaped+'"\nIcon=applications-games\nTerminal=false\nCategories=Game;\n')
    (out/'Uninstall.MagicShelf.desktop').chmod(0o755)
    update={'schema_version':1,'version':VERSION,'artifacts':{arch:{'url':f'https://github.com/{REPO}/releases/download/v{VERSION}/{archive.name}','sha256':sha(archive),'size_bytes':archive.stat().st_size}}}
    (out/'framework.json').write_text(json.dumps(update,indent=2)+'\n')
    assets=[archive,out/'framework.json',out/'catalog.json',bootstrap,out/'Install.MagicShelf.desktop',uninstaller,out/'Uninstall.MagicShelf.desktop']
    (out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in sorted(assets)))
    print(json.dumps({'version':VERSION,'architecture':arch,'framework':str(archive),'desktop':str(out/'Install.MagicShelf.desktop')},indent=2))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--architecture',choices=['aarch64','x86_64'],required=True);build(parser.parse_args().architecture)
