import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from magicshelf.contracts import ContractError, manifest, PERMISSIONS
from magicshelf.manager import Manager
from magicshelf.server import dispatch
from magicshelf.storefront import MEDIA, BUILTINS, decorate, media_path, valid_png
from test_framework import FakeSystem, meta, package

class StorefrontTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
        self.manager=Manager(self.path/'home',self.path/'runtime',FakeSystem())
        self.source='https://raw.githubusercontent.com/creator/creations/main/catalog.json'
        self.key='org.test.toy'
        self.archives={}
    def tearDown(self):self.temp.cleanup()
    def release(self, ver, permissions=None, source=None):
        item=meta(ver)
        if permissions:item['permissions']=permissions
        archive=self.path/(ver+'.zip');digest=package(archive,item)
        item.update(url='https://github.com/creator/creations/releases/download/v'+ver+'/creation.magicshelf',sha256=digest,size_bytes=archive.stat().st_size,catalog_url=source or self.source)
        self.archives[item['url']]=archive
        self.manager.state['catalog']=[item]
        return item
    def download(self,url,target,limit,progress=None):
        if progress:progress(0)
        shutil.copy2(self.archives[url],target)
        if progress:progress(target.stat().st_size)
    def subscribe(self):
        with patch('magicshelf.manager.download',side_effect=self.download):
            return self.manager.subscribe(self.key,True,['vr-overlay'])
    def test_subscribe_downloads_and_persists_without_turning_on(self):
        self.release('1.0.0');state=self.subscribe()
        self.assertTrue(state['modules'][0]['subscribed'])
        self.assertFalse(state['modules'][0]['enabled'])
        restored=Manager(self.path/'home',self.path/'runtime',FakeSystem())
        self.assertEqual(restored.state['subscriptions'][self.key]['catalog_url'],self.source)
        self.assertTrue(restored.modulepath(self.key,'1.0.0').is_dir())
    def test_download_progress_is_published_before_automatic_install(self):
        item=self.release('1.0.0');observed=[]
        publish=self.manager.publish
        def record():
            publish()
            state=json.loads((self.manager.runtime/'ui-state.json').read_text())
            if state['transfer']:observed.append(state)
        def downloading(url,target,limit,progress):
            progress(0)
            self.assertEqual(json.loads((self.manager.runtime/'ui-state.json').read_text())['transfer']['stage'],'downloading')
            shutil.copy2(self.archives[url],target)
            progress(target.stat().st_size)
        with patch.object(self.manager,'publish',side_effect=record),patch('magicshelf.manager.download',side_effect=downloading):
            result=self.manager.subscribe(self.key,True,item['permissions'])
        stages=[s['transfer']['stage'] for s in observed]
        self.assertLess(stages.index('downloading'),stages.index('checking'))
        self.assertLess(stages.index('checking'),stages.index('installing'))
        self.assertLess(stages.index('installing'),stages.index('complete'))
        for state in observed:
            if state['transfer']['stage']=='complete':
                self.assertTrue(next(m for m in state['modules'] if m['id']==self.key)['installed'])
        self.assertEqual(result['transfer']['received_bytes'],item['size_bytes'])
        self.assertFalse(result['transfer']['active']);self.assertFalse(result['busy'])
        self.assertTrue(result['modules'][0]['installed'])
    def test_bad_download_never_reports_ready_and_preserves_previous_install(self):
        self.release('1.0.0');self.subscribe()
        item=self.release('1.1.0');item['sha256']='0'*64
        with patch('magicshelf.manager.download',side_effect=self.download),self.assertRaisesRegex(ContractError,'checksum'):
            self.manager.subscribe(self.key,True,item['permissions'])
        state=self.manager.snapshot()
        self.assertEqual(state['transfer']['stage'],'failed');self.assertFalse(state['transfer']['active'])
        self.assertEqual(self.manager.state['modules'][self.key]['version'],'1.0.0')
        self.assertFalse(self.manager.modulepath(self.key,'1.1.0').exists())
    def test_permissions_have_plain_language_for_installs_and_updates(self):
        item=meta();item['permissions']=sorted(PERMISSIONS)
        result=decorate({**item,'update':item},self.manager.root)
        for value in (result,result['update']):
            self.assertEqual([p['id'] for p in value['permission_details']],sorted(PERMISSIONS))
            for permission in value['permission_details']:
                self.assertNotEqual(permission['title'],permission['id'])
                self.assertGreater(len(permission['description']),30)
            self.assertEqual(value['permissions'],sorted(PERMISSIONS))
    def test_automatic_update_keeps_off_and_saved_data(self):
        self.release('1.0.0');self.subscribe()
        data=self.manager.root/'module-data'/self.key;data.mkdir(parents=True);(data/'save').write_text('my pet')
        self.release('1.1.0')
        with patch('magicshelf.manager.download',side_effect=self.download):self.manager.sync_subscriptions(refresh=False)
        state=self.manager.state['modules'][self.key]
        self.assertEqual(state['version'],'1.1.0');self.assertFalse(state['enabled'])
        self.assertEqual((data/'save').read_text(),'my pet')
        self.assertEqual(state['previous_version'],'1.0.0')
    def test_auto_update_needs_review_for_new_permissions(self):
        self.release('1.0.0');self.subscribe();self.release('1.1.0',['vr-overlay','network'])
        with patch('magicshelf.manager.download') as download:self.manager.sync_subscriptions(refresh=False)
        download.assert_not_called();self.assertEqual(self.manager.state['modules'][self.key]['version'],'1.0.0')
        self.assertIn('permissions review',self.manager.update_message)
        with patch('magicshelf.manager.download',side_effect=self.download):self.manager.subscribe(self.key,True,['vr-overlay','network'])
        self.assertEqual(self.manager.state['subscriptions'][self.key]['permissions'],['vr-overlay','network'])
    def test_unsubscribe_keeps_install_and_prevents_future_updates(self):
        self.release('1.0.0');self.subscribe();self.manager.subscribe(self.key,False);self.release('2.0.0')
        with patch('magicshelf.manager.download') as download:self.manager.sync_subscriptions(refresh=False)
        download.assert_not_called();self.assertEqual(self.manager.state['modules'][self.key]['version'],'1.0.0')
        self.assertTrue(self.manager.modulepath(self.key,'1.0.0').is_dir())
    def test_background_failure_keeps_previous_version_and_subscription(self):
        self.release('1.0.0');self.subscribe();self.release('1.1.0')
        with patch('magicshelf.manager.download',side_effect=OSError('offline')):self.manager.sync_subscriptions(refresh=False)
        self.assertEqual(self.manager.state['modules'][self.key]['version'],'1.0.0')
        self.assertIn(self.key,self.manager.state['subscriptions']);self.assertIn('offline',self.manager.snapshot()['modules'][0]['update_note'])
        self.assertIn('retry',self.manager.update_message)
    def test_failed_first_download_does_not_create_subscription(self):
        self.release('1.0.0')
        with patch('magicshelf.manager.download',side_effect=OSError('offline')),self.assertRaises(OSError):self.manager.subscribe(self.key,True,['vr-overlay'])
        self.assertNotIn(self.key,self.manager.state['modules']);self.assertNotIn(self.key,self.manager.state['subscriptions'])
    def test_subscription_source_cannot_be_replaced(self):
        self.release('1.0.0');self.subscribe();self.release('9.0.0',source='https://github.com/other/catalog')
        with patch('magicshelf.manager.download') as download:self.manager.sync_subscriptions(refresh=False)
        download.assert_not_called();self.assertEqual(self.manager.state['modules'][self.key]['version'],'1.0.0')
        with self.assertRaises(ContractError):self.manager.subscribe(self.key,True,['vr-overlay'])
    def test_removal_cancels_auto_redownload(self):
        self.release('1.0.0');self.subscribe();self.manager.remove(self.key)
        self.assertIsNone(self.manager.snapshot()['transfer'])
        with patch('magicshelf.manager.download') as download:self.manager.sync_subscriptions(refresh=False)
        download.assert_not_called();self.assertNotIn(self.key,self.manager.state['subscriptions'])
    def test_local_builds_have_real_gallery_and_no_fake_download(self):
        for key in BUILTINS:
            self.manager.state['modules'][key]={'adapter':True,'version':'0.1.0','enabled':False}
        for item in self.manager.snapshot()['modules']:
            self.assertFalse(item['subscription_available']);self.assertEqual(item['update_mode'],'local');self.assertNotIn('price_label',item)
            self.assertGreaterEqual(len(item['screenshots']),2)
            for image in item['screenshots']:
                path=media_path(image['url'],self.manager.root);valid_png(path)
                self.assertEqual(path.resolve(),Path(image['path']))
        with self.assertRaises(ContractError):self.manager.subscribe('org.magicshelf.digital-partner',True,[])
    def test_metadata_accepts_credits_and_rejects_executable_links_or_paid_items(self):
        value=meta();value.update(screenshots=[{'url':'https://raw.githubusercontent.com/creator/repo/main/image.png','caption':'Preview'}],links=[{'label':'GitHub','url':'https://github.com/creator/repo'}],credits=[{'name':'Artist','role':'3D model','url':'https://x.com/artist','support_url':'https://ko-fi.com/artist'}]);manifest(value)
        for url in ['javascript:alert(1)','file:///etc/passwd','http://github.com/creator/repo','https://name:password@github.com/a']:
            bad=copy.deepcopy(value);bad['links'][0]['url']=url
            with self.subTest(url=url),self.assertRaises(ValueError):manifest(bad)
        bad=copy.deepcopy(value);bad['price']=10
        with self.assertRaises(ValueError):manifest(bad)
    def test_media_route_is_allowlisted(self):
        for route in ['/media/builtin/../../state.json','/media/cached/../state.json','/media/builtin/unknown.png','/media/cached/%2e%2e.png','/media/builtin/phone.png?other']:
            with self.subTest(route=route),self.assertRaises(ValueError):media_path(route,self.manager.root)
    def test_catalog_cannot_select_a_local_image(self):
        item=meta()
        for asset in ['phone.png',str(MEDIA/'phone.png')]:
            item['screenshots']=[{'url':'https://github.com/creator/repo/image.png','asset':asset}]
            self.assertEqual(decorate(item,self.manager.root)['screenshots'],[])
    def test_links_resolve_from_metadata_not_supplied_command(self):
        key='org.magicshelf.digital-partner';self.manager.state['modules'][key]={'adapter':True,'version':'0.1.0','enabled':False}
        with patch('magicshelf.manager.subprocess.run') as run:
            dispatch(self.manager,{'api_version':1,'method':'module.link','params':{'id':key,'index':3}})
            self.assertEqual(run.call_args.args[0],['xdg-open','https://x.com/jojogape'])
            with self.assertRaises(ValueError):self.manager.open_link(key,-1)
    def test_png_dimensions_are_bounded(self):
        p=self.path/'large.png';p.write_bytes(b'\x89PNG\r\n\x1a\n'+b'\0\0\0\rIHDR'+(100000).to_bytes(4,'big')*2)
        with self.assertRaises(ValueError):valid_png(p)
    def test_app_launcher_opens_native_dashboard(self):
        from magicshelf.__main__ import main
        with patch('sys.argv',['magicshelf','open']),patch('magicshelf.__main__.subprocess.run') as run:
            main()
        self.assertEqual(run.call_count,1)
        self.assertEqual(Path(run.call_args.args[0][0]).name,'magicshelf-vr-launch')
        self.assertNotIn('xdg-open',run.call_args.args[0])
    def test_api_subscription_is_real_and_type_checked(self):
        self.release('1.0.0')
        with patch('magicshelf.manager.download',side_effect=self.download):
            state=dispatch(self.manager,{'api_version':1,'method':'module.subscribe','params':{'id':self.key,'subscribed':True,'permissions':['vr-overlay']}})
        self.assertTrue(state['modules'][0]['subscribed'])
        with self.assertRaises(ValueError):self.manager.subscribe(self.key,'yes',[])

if __name__=='__main__':unittest.main()
