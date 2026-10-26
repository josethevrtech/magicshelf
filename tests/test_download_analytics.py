import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('download_analytics',Path(__file__).resolve().parents[1]/'tools/download_analytics.py')
analytics=importlib.util.module_from_spec(spec);spec.loader.exec_module(analytics)


class DownloadAnalyticsTests(unittest.TestCase):
    def release(self):
        def asset(id,name,count):return dict(id=id,name=name,download_count=count,size=100)
        return dict(tag_name='v1.0.0',published_at='2026-10-26T00:00:00Z',draft=False,prerelease=False,
                    assets=[asset(1,'org.test-1.magicshelf',7),asset(2,'catalog.json',900),
                            asset(3,'preview.png',40),asset(4,'SHA256SUMS',20),asset(5,'Install.MagicShelf.desktop',3)])

    def test_catalog_polling_does_not_inflate_package_popularity(self):
        project=analytics.collect('owner/repo',lambda _: [self.release()])
        self.assertEqual(project['package_downloads'],7)
        self.assertEqual(project['installer_downloads'],3)
        self.assertEqual(len(project['releases'][0]['assets']),1)

    def test_drafts_are_excluded_and_both_framework_architectures_count(self):
        item=self.release();item['assets']=[dict(id=10,name='magicshelf-1.0.0-linux-aarch64.tar.gz',download_count=4,size=100),dict(id=11,name='magicshelf-1.0.0-linux-x86_64.tar.gz',download_count=6,size=100)]
        draft={**self.release(),'draft':True}
        project=analytics.collect('owner/repo',lambda _:[item,draft])
        self.assertEqual(project['package_downloads'],10)

    def test_full_pages_are_followed(self):
        calls=[]
        def fetch(url):
            calls.append(url)
            return [self.release()]*100 if len(calls)==1 else []
        self.assertEqual(analytics.collect('owner/repo',fetch)['package_downloads'],700)
        self.assertIn('page=2',calls[-1])

    def test_first_snapshot_is_a_baseline_not_a_daily_measurement(self):
        snapshot=dict(collected_at='now',projects=[analytics.collect('owner/repo',lambda _:[self.release()])])
        text=analytics.report(snapshot)
        self.assertIn('Baseline',text);self.assertIn('not unique people',text)
        self.assertIn('No analytics code runs on user devices',text)
        self.assertIn('| 0 |',analytics.report(snapshot,snapshot))

    def test_api_errors_are_not_silently_reported_as_zero_downloads(self):
        def offline(_):raise OSError('offline')
        with self.assertRaises(OSError):analytics.collect('owner/repo',offline)
