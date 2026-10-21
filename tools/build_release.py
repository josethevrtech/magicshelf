#!/usr/bin/env python3
"""Build immutable framework/module assets and a pinned single-file launcher."""
import argparse, base64, hashlib, json, os, shutil, stat, tarfile, tempfile, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
VERSION='0.1.2'
REPO='josethevrtech/magicshelf'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def build(arch):
    out=ROOT/'dist';out.mkdir(exist_ok=True)
    meta=json.loads((ROOT/'examples/pocket-clock/module.json').read_text());meta['architecture']=arch
    module=out/f'pocket-clock-{meta["version"]}-linux-{arch}.magicshelf'
    with zipfile.ZipFile(module,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data,mode in [('module.json',(json.dumps(meta,indent=2,sort_keys=True)+'\n').encode(),0o100644),('bin/pocket-clock',(ROOT/'build/modules/pocket-clock/bin/pocket-clock').read_bytes(),0o100755),('LICENSE',(ROOT/'LICENSE').read_bytes(),0o100644)]:
            info=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0));info.external_attr=mode<<16;info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data)
    url=f'https://github.com/{REPO}/releases/download/v{VERSION}/{module.name}'
    item={**meta,'url':url,'sha256':sha(module),'size_bytes':module.stat().st_size}
    catalog={'schema_version':1,'name':'MagicShelf by josethevrtech','modules':[item]}
    (out/'example-catalog.json').write_text(json.dumps(catalog,indent=2)+'\n')
    catalog['modules']=[]
    (out/'catalog.json').write_text(json.dumps(catalog,indent=2)+'\n')
    with tempfile.TemporaryDirectory() as temp:
        payload=Path(temp)/'magicshelf';payload.mkdir()
        for name in ['magicshelf','bin']:
            shutil.copytree(ROOT/name,payload/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        shutil.copy2(ROOT/'build/bin/magicshelf-vr',payload/'bin/magicshelf-vr')
        for name in ['shelf.json','install.py','uninstall.py','LICENSE','OPENVR-LICENSE.txt','build/icon.png']:
            shutil.copy2(ROOT/name,payload/Path(name).name)
        (payload/'bundled').mkdir()
        shutil.copy2(out/'catalog.json',payload/'catalog.json')
        release={'schema_version':1,'version':VERSION,'api_version':1,'architecture':arch,'bundled':[]}
        for path in (payload/'bin').iterdir():path.chmod(0o755)
        release['files']={str(p.relative_to(payload)):sha(p) for p in sorted(payload.rglob('*')) if p.is_file()}
        (payload/'release.json').write_text(json.dumps(release,indent=2)+'\n')
        archive=out/f'magicshelf-{VERSION}-linux-{arch}.tar.gz'
        with tarfile.open(archive,'w:gz') as tar:tar.add(payload,arcname='magicshelf')
    # All files are verified before any framework code runs. The .desktop pins this bootstrap.
    bootstrap=out/'install-magicshelf.py'
    bootstrap.write_text((ROOT/'tools/bootstrap.py.in').read_text().replace('@URL@',f'https://github.com/{REPO}/releases/download/v{VERSION}/{archive.name}').replace('@SHA256@',sha(archive)).replace('@ARCH@',arch))
    launcher_source="""import hashlib,pathlib,subprocess,tempfile,urllib.request
try:
    with tempfile.TemporaryDirectory(prefix='magicshelf-') as temp:
        path=pathlib.Path(temp)/'install.py'
        with urllib.request.urlopen('@BOOTSTRAP_URL@',timeout=45) as response:
            data=response.read(1048577)
        if len(data)>1048576 or hashlib.sha256(data).hexdigest()!='@BOOTSTRAP_SHA@':
            raise RuntimeError('Installer verification failed; nothing was installed.')
        path.write_bytes(data)
        subprocess.run(['python3',str(path)],check=True)
except Exception as error:
    print('MagicShelf:',error)
    try:subprocess.run(['kdialog','--error',str(error)],check=False)
    except FileNotFoundError:pass
    raise SystemExit(1)
""".replace('@BOOTSTRAP_URL@',f'https://github.com/{REPO}/releases/download/v{VERSION}/install-magicshelf.py').replace('@BOOTSTRAP_SHA@',sha(bootstrap))
    # Base64 is just argument quoting for Desktop Entry's Exec grammar.
    code="import base64;exec(base64.b64decode('"+base64.b64encode(launcher_source.encode()).decode()+"'))"
    escaped=code.replace('\\','\\\\').replace('"','\\"').replace('%','%%')
    (out/'Install MagicShelf.desktop').write_text('[Desktop Entry]\nType=Application\nName=Install MagicShelf\nComment=Install the MagicShelf shelf and module library\nExec=python3 -c "'+escaped+'"\nIcon=applications-games\nTerminal=true\nCategories=Game;\n')
    (out/'Install MagicShelf.desktop').chmod(0o755)
    assets=[out/'example-catalog.json',module,archive,out/'catalog.json',bootstrap,out/'Install MagicShelf.desktop']
    (out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in sorted(assets)))
    print(json.dumps({'version':VERSION,'architecture':arch,'framework':str(archive),'module':str(module),'desktop':str(out/'Install MagicShelf.desktop')},indent=2))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--architecture',choices=['aarch64','x86_64'],required=True);build(parser.parse_args().architecture)
