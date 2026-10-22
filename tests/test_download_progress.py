import io
import urllib.error
import http.client
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from magicshelf.packages import download
from magicshelf.contracts import ContractError


class DownloadProgressTests(unittest.TestCase):
    def transfer(self, content, limit):
        url='https://github.com/example/creation/releases/download/v1/package.magicshelf'
        response=io.BytesIO(content)
        response.geturl=lambda:url
        received=[]
        with tempfile.TemporaryDirectory() as temp,patch('urllib.request.build_opener',return_value=Mock(open=Mock(return_value=response))):
            target=Path(temp)/'download'
            download(url,target,limit,progress=received.append)
            self.assertEqual(target.read_bytes(),content)
        return received

    def test_reports_actual_bytes_and_final_short_chunk(self):
        self.assertEqual(self.transfer(b'x'*140001,140001),[0,65536,131072,140001])

    def test_progress_does_not_disable_the_download_size_limit(self):
        with self.assertRaisesRegex(ContractError,'declared limit'):
            self.transfer(b'x'*65537,65536)

    def response(self, content, length=None):
        response = io.BytesIO(content)
        response.geturl = lambda: 'https://github.com/example/creation/package.magicshelf'
        response.headers = {'Content-Length': str(length or len(content))}
        return response

    def test_short_connection_retries_from_zero_without_partial_bytes(self):
        responses = [self.response(b'bad', 8), self.response(b'complete')]
        opener = Mock(open=Mock(side_effect=responses))
        received = []
        with tempfile.TemporaryDirectory() as temp, patch('urllib.request.build_opener', return_value=opener), patch('magicshelf.packages.time.sleep'):
            target = Path(temp)/'download'
            download('https://github.com/example/creation/package.magicshelf', target, 8, progress=received.append)
            self.assertEqual(target.read_bytes(), b'complete')
        self.assertEqual(opener.open.call_count, 2)
        self.assertEqual(received, [0, 3, 0, 8])

    def test_transient_service_failure_retries_but_missing_asset_does_not(self):
        url = 'https://github.com/example/creation/package.magicshelf'
        for status, expected in [(503, 3), (404, 1)]:
            opener = Mock(open=Mock(side_effect=lambda *a, **k: (_ for _ in ()).throw(urllib.error.HTTPError(url, status, 'failed', {}, None))))
            with self.subTest(status=status), tempfile.TemporaryDirectory() as temp, patch('urllib.request.build_opener', return_value=opener), patch('magicshelf.packages.time.sleep'), self.assertRaises(urllib.error.HTTPError):
                download(url, Path(temp)/'download')
            self.assertEqual(opener.open.call_count, expected)

    def test_exhausted_short_download_removes_partial_file(self):
        opener = Mock(open=Mock(side_effect=lambda *a, **k: self.response(b'bad', 20)))
        with tempfile.TemporaryDirectory() as temp, patch('urllib.request.build_opener', return_value=opener), patch('magicshelf.packages.time.sleep'):
            target = Path(temp)/'download'
            with self.assertRaises(http.client.IncompleteRead):
                download('https://github.com/example/creation/package.magicshelf', target)
            self.assertFalse(target.exists())
        self.assertEqual(opener.open.call_count, 3)

    def test_existing_file_is_never_removed(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)/'existing'; target.write_text('keep')
            with self.assertRaises(FileExistsError):
                download('https://github.com/example/creation/package.magicshelf', target)
            self.assertEqual(target.read_text(), 'keep')
