import io
import json
from pathlib import Path
import types
import unittest
from unittest.mock import patch

source=(Path(__file__).resolve().parents[1]/'tools/bootstrap.py.in').read_text().replace('@ARCH@','aarch64')
bootstrap=types.ModuleType('bootstrap');exec(compile(source,'bootstrap','exec'),bootstrap.__dict__)

class BootstrapTests(unittest.TestCase):
    def manifest(self,version='9.8.7'):
        return {'schema_version':1,'version':version,'artifacts':{'aarch64':{'url':f'https://github.com/josethevrtech/magicshelf/releases/download/v{version}/magicshelf-{version}-linux-aarch64.tar.gz','sha256':'a'*64,'size_bytes':1000}}}
    def latest(self,data):
        with patch.object(bootstrap.urllib.request,'urlopen',return_value=io.BytesIO(json.dumps(data).encode())):
            return bootstrap.latest_release()
    def test_saved_bootstrap_selects_a_newer_release(self):
        self.assertEqual(self.latest(self.manifest())['version'],'9.8.7')
    def test_rejects_nonofficial_archive(self):
        data=self.manifest();data['artifacts']['aarch64']['url']='https://example.org/install.tar.gz'
        with self.assertRaises(RuntimeError):self.latest(data)
    def test_rejects_missing_digest_or_invalid_size(self):
        for field,value in [('sha256',''),('size_bytes',0),('size_bytes',True),('size_bytes',100*1024*1024+1)]:
            with self.subTest(field=field,value=value):
                data=self.manifest();data['artifacts']['aarch64'][field]=value
                with self.assertRaises(RuntimeError):self.latest(data)
    def test_rejects_oversized_manifest(self):
        with patch.object(bootstrap.urllib.request,'urlopen',return_value=io.BytesIO(b' '*65537)):
            with self.assertRaises(RuntimeError):bootstrap.latest_release()
