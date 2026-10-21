#!/usr/bin/env python3
"""Create an independent SDK-pinned creation from the working clock example."""
import argparse,json,re,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def create(destination, identity, name, repository, revision=None):
    import sys
    sys.path.insert(0,str(ROOT))
    from magicshelf.contracts import manifest,require
    require(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository),'Use owner/repository')
    revision=revision or subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    require(re.fullmatch(r'[0-9a-f]{40}',revision),'Pin a full SDK commit SHA')
    meta=json.loads((ROOT/'examples/pocket-clock/module.json').read_text())
    meta.update(id=identity,name=name,author=repository.split('/')[0],entrypoint='bin/creation',description='A free creation for MagicShelf.',version='0.1.0')
    manifest(meta)
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=False)
    for folder in ['src','tools','.github/workflows']:(destination/folder).mkdir(parents=True)
    (destination/'module.json').write_text(json.dumps(meta,indent=2)+'\n')
    (destination/'sdk.lock.json').write_text(json.dumps({'repository':'https://github.com/josethevrtech/magicshelf.git','revision':revision,'sdk_version':'1.0.0'},indent=2)+'\n')
    source=(ROOT/'examples/pocket-clock/main.cpp').read_text().replace('"Pocket Clock"',json.dumps(name)).replace('"POCKET CLOCK"',json.dumps(name.upper()))
    (destination/'src/main.cpp').write_text(source)
    (destination/'.gitignore').write_text('build/\ndist/\nvendor/\n__pycache__/\n*.pyc\n')
    shutil.copy2(ROOT/'LICENSE',destination/'LICENSE')
    (destination/'tools/fetch_sdk.py').write_text('''#!/usr/bin/env python3
import json,pathlib,re,subprocess
root=pathlib.Path(__file__).resolve().parents[1]
lock=json.loads((root/'sdk.lock.json').read_text())
if lock['repository']!='https://github.com/josethevrtech/magicshelf.git' or not re.fullmatch(r'[0-9a-f]{40}',lock['revision']):
    raise SystemExit('Invalid SDK pin')
target=root/'vendor/magicshelf'
if target.exists():
    actual=subprocess.check_output(['git','-C',str(target),'rev-parse','HEAD'],text=True).strip()
    dirty=subprocess.check_output(['git','-C',str(target),'status','--porcelain'],text=True).strip()
    if actual!=lock['revision'] or dirty:raise SystemExit('Existing SDK differs from pin; move it aside before fetching')
else:
    target.mkdir(parents=True)
    subprocess.run(['git','init',str(target)],check=True)
    subprocess.run(['git','-C',str(target),'fetch','--depth=1',lock['repository'],lock['revision']],check=True)
    subprocess.run(['git','-C',str(target),'checkout','--detach',lock['revision']],check=True)
print('SDK pinned at',lock['revision'])
''')
    (destination/'build.sh').write_text('''#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
sdk="${MAGICSHELF_SDK_DIR:-$PWD/vendor/magicshelf}"
case "$(uname -m)" in aarch64) platform=linuxarm64;; x86_64) platform=linux64;; *) exit 1;; esac
vr="${OPENVR_LIB_DIR:-/opt/steamvr/bin/$platform}"
mkdir -p build/package/bin
c++ -O2 -std=c++17 -pthread -I"$sdk/native" src/main.cpp -o build/package/bin/creation \
  -L"$vr" -lopenvr_api -Wl,-rpath,/opt/steamvr/bin/"$platform" $(pkg-config --cflags --libs egl glesv2 cairo json-c)
cp LICENSE build/package/
python3 - <<'META'
import json,platform
from pathlib import Path
meta=json.loads(Path('module.json').read_text());meta['architecture']=platform.machine()
Path('build/package/module.json').write_text(json.dumps(meta,indent=2)+'\\n')
META
python3 "$sdk/tools/package_creation.py" build/package --repository '''+repository+''' --output dist
''')
    (destination/'build.sh').chmod(0o755)
    (destination/'.github/workflows/release.yml').write_text('''name: Creation package
on:
  push:
    branches: [main]
    tags: ['v*']
  pull_request:
permissions:
  contents: read
jobs:
  frame:
    runs-on: ubuntu-24.04-arm
    steps:
      - uses: actions/checkout@v4
      - run: python3 tools/fetch_sdk.py
      - run: sudo apt-get update && sudo apt-get install -y g++ pkg-config libegl1-mesa-dev libgles2-mesa-dev libcairo2-dev libjson-c-dev
      - uses: actions/checkout@v4
        with:
          repository: ValveSoftware/openvr
          ref: 0924064316de3effbcd1acf1e309182a2deb1c05
          path: vendor/openvr
      - run: ./build.sh
        env:
          OPENVR_LIB_DIR: ${{ github.workspace }}/vendor/openvr/bin/linuxarm64
      - name: Verify tag
        if: startsWith(github.ref, 'refs/tags/')
        run: python3 -c 'import json,os; assert os.environ["GITHUB_REF_NAME"] == "v"+json.load(open("module.json"))["version"]'
      - uses: actions/upload-artifact@v4
        with:
          name: frame-package
          path: dist/*
  publish:
    if: startsWith(github.ref, 'refs/tags/')
    needs: frame
    runs-on: ubuntu-24.04
    permissions:
      contents: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: frame-package
          path: dist
      - run: gh release create "$GITHUB_REF_NAME" dist/* --repo "$GITHUB_REPOSITORY" --generate-notes
        env:
          GH_TOKEN: ${{ github.token }}
''')
    (destination/'README.md').write_text('# '+name+'\n\nA free creation for MagicShelf on SteamOS and Steam Frame.\n\nRun `python3 tools/fetch_sdk.py`, then `./build.sh`.\n\nDependencies: C++17, pkg-config, EGL/GLES3, Cairo, json-c and SteamVR.\nThe SDK is pinned in `sdk.lock.json`; local SDK development may set\n`MAGICSHELF_SDK_DIR`. Bump `module.json` and tag `vX.Y.Z` to release\nthis creation independently. Follow its release `catalog.json` in MagicShelf.\n\n[Creator guide](https://github.com/josethevrtech/magicshelf/blob/main/docs/CREATING.md)\n')
    return destination

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('destination',type=Path);p.add_argument('--id',required=True);p.add_argument('--name',required=True);p.add_argument('--repository',required=True);p.add_argument('--sdk-revision')
    a=p.parse_args();print(create(a.destination,a.id,a.name,a.repository,a.sdk_revision))
