#!/usr/bin/env python3
"""Build immutable framework assets and a pinned single-file launcher."""
import argparse, base64, gzip, hashlib, json, os, shutil, stat, tarfile, tempfile, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
VERSION='0.3.17'
REPO='josethevrtech/magicshelf'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def copy_public(source,target):
    if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(ROOT.resolve()):
        raise RuntimeError('Release source must be a regular file inside the checkout: '+str(source.relative_to(ROOT)))
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,target)

def build(arch):
    out=ROOT/'dist';out.mkdir(exist_ok=True)
    # Creation packages and catalogs are released by their own repositories.
    copy_public(ROOT/'catalog.json', out/'catalog.json')
    with tempfile.TemporaryDirectory() as temp:
        payload=Path(temp)/'magicshelf';payload.mkdir()
        # Never collect the working directory wholesale. Only reviewed runtime
        # files can enter a public download, even if local state sits beside them.
        for name in json.loads((ROOT/'tools/framework-files.json').read_text()):
            source=ROOT/name
            target=payload/name;target.parent.mkdir(parents=True,exist_ok=True)
            copy_public(source,target)
        copy_public(ROOT/'build/bin/magicshelf-vr',payload/'bin/magicshelf-vr')
        for name in ['collections.json','shelf.json','install.py','uninstall.py','LICENSE','OPENVR-LICENSE.txt','build/icon.png']:
            copy_public(ROOT/name,payload/Path(name).name)
        (payload/'bundled').mkdir()
        shutil.copy2(out/'catalog.json',payload/'catalog.json')
        release={'schema_version':1,'version':VERSION,'api_version':1,'architecture':arch,'bundled':[]}
        for path in (payload/'bin').iterdir():path.chmod(0o755)
        release['files']={str(p.relative_to(payload)):sha(p) for p in sorted(payload.rglob('*')) if p.is_file()}
        (payload/'release.json').write_text(json.dumps(release,indent=2)+'\n')
        archive=out/f'magicshelf-{VERSION}-linux-{arch}.tar.gz'
        def public_metadata(info):
            info.uid=info.gid=0;info.uname=info.gname='';info.mtime=0
            info.pax_headers={}
            return info
        with archive.open('wb') as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as compressed,tarfile.open(fileobj=compressed,mode='w') as tar:
            tar.add(payload,arcname='magicshelf',filter=public_metadata)
    # The reusable launcher pins this small bootstrap. It discovers and verifies
    # the latest archive each time, so a saved desktop icon never installs old code.
    bootstrap=out/'install-magicshelf.py'
    bootstrap.write_text((ROOT/'tools/bootstrap.py.in').read_text().replace('@ARCH@',arch))
    launcher_source="""import base64,hashlib,pathlib,subprocess,sys,tempfile,urllib.parse,urllib.request
try:
    icon=pathlib.Path.home()/'.local/share/icons/hicolor/512x512/apps/com.josethevrtech.magicshelf.png'
    icon.parent.mkdir(parents=True,exist_ok=True)
    icon.write_bytes(base64.b64decode('@ICON_DATA@'))
    # Refresh this shortcut after the icon is registered. %k is supplied by KDE.
    if len(sys.argv)>1:
        entry=pathlib.Path(urllib.parse.unquote(urllib.parse.urlparse(sys.argv[1]).path))
        if entry.is_file() and not entry.is_symlink() and entry.suffix=='.desktop' and 'X-MagicShelf-Launcher=true' in entry.read_text():
            entry.touch()
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
""".replace('@BOOTSTRAP_URL@',f'https://github.com/{REPO}/releases/download/v{VERSION}/install-magicshelf.py').replace('@BOOTSTRAP_SHA@',sha(bootstrap)).replace('@ICON_DATA@',base64.b64encode((ROOT/'build/icon.png').read_bytes()).decode())
    # Base64 is just argument quoting for Desktop Entry's Exec grammar.
    code="import base64;exec(base64.b64decode('"+base64.b64encode(launcher_source.encode()).decode()+"'))"
    escaped=code.replace('\\','\\\\').replace('"','\\"').replace('%','%%')
    (out/'Install.MagicShelf.desktop').write_text('[Desktop Entry]\nType=Application\nName=Install MagicShelf\nComment=Install MagicShelf\nExec=python3 -c "'+escaped+'" %k\nIcon=com.josethevrtech.magicshelf\nTerminal=false\nCategories=Game;\nX-MagicShelf-Launcher=true\n')
    (out/'Install.MagicShelf.desktop').chmod(0o755)
    # Standalone recovery uninstaller also works after a partial old removal.
    uninstaller=out/'uninstall-magicshelf.py'
    # The recovery download must also work when no framework is installed.
    uninstaller.write_text((ROOT/'uninstall.py').read_text().replace(
        'from magicshelf.session import service_environment',
        (ROOT/'magicshelf/session.py').read_text()))
    uninstall_source=launcher_source.replace('/install-magicshelf.py', '/uninstall-magicshelf.py').replace(sha(bootstrap),sha(uninstaller)).replace("str(path)]", "str(path),'--gui']")
    code="import base64;exec(base64.b64decode('"+base64.b64encode(uninstall_source.encode()).decode()+"'))"
    escaped=code.replace('\\','\\\\').replace('"','\\"').replace('%','%%')
    (out/'Uninstall.MagicShelf.desktop').write_text('[Desktop Entry]\nType=Application\nName=Uninstall MagicShelf\nComment=Remove MagicShelf and keep saved data\nExec=python3 -c "'+escaped+'" %k\nIcon=com.josethevrtech.magicshelf\nTerminal=false\nCategories=Game;\nX-MagicShelf-Launcher=true\n')
    (out/'Uninstall.MagicShelf.desktop').chmod(0o755)
    update={'schema_version':1,'version':VERSION,'artifacts':{arch:{'url':f'https://github.com/{REPO}/releases/download/v{VERSION}/{archive.name}','sha256':sha(archive),'size_bytes':archive.stat().st_size}}}
    (out/'framework.json').write_text(json.dumps(update,indent=2)+'\n')
    shutil.copy2(ROOT/'branding/magicshelf.svg',out/'MagicShelf.svg')
    shutil.copy2(ROOT/'build/icon.png',out/'MagicShelf.png')
    assets=[archive,out/'framework.json',out/'catalog.json',bootstrap,out/'Install.MagicShelf.desktop',uninstaller,out/'Uninstall.MagicShelf.desktop',out/'MagicShelf.svg',out/'MagicShelf.png']
    bundle=out/'MagicShelf-icons-and-launchers.zip'
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as z:
        for name in ('MagicShelf.svg','MagicShelf.png','Install.MagicShelf.desktop','Uninstall.MagicShelf.desktop'):
            info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.external_attr=(0o100755 if name.endswith('.desktop') else 0o100644)<<16
            z.writestr(info,(out/name).read_bytes())
        z.writestr(zipfile.ZipInfo('README.txt',(2026,1,1,0,0,0)),(ROOT/'branding/README.txt').read_bytes())
    assets.append(bundle)
    (out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in sorted(assets)))
    print(json.dumps({'version':VERSION,'architecture':arch,'framework':str(archive),'desktop':str(out/'Install.MagicShelf.desktop')},indent=2))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--architecture',choices=['aarch64','x86_64'],required=True);build(parser.parse_args().architecture)
