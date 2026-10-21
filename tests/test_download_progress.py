import io
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
