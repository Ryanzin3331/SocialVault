import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app' / 'src' / 'main' / 'python'))
from android_bridge import download_source, UserCancelled
from socialvault.core import SocialVaultError

class Listener:
    def __init__(self, cancel=False):
        self.cancel = cancel
        self.events = []
    def isCancelled(self): return self.cancel
    def onProgress(self, stage, pct): self.events.append((stage, pct))


def factory(ext='mp4', content=b'video'):
    class FakeYoutubeDL:
        def __init__(self, opts): self.opts = opts
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def extract_info(self, url, download):
            path = Path(self.opts['outtmpl'].replace('%(id)s', '123').replace('%(ext)s', ext))
            self.opts['progress_hooks'][0]({'status': 'downloading', 'downloaded_bytes': 5, 'total_bytes': 10})
            path.write_bytes(content)
            self.opts['progress_hooks'][0]({'status': 'finished'})
            return {'id':'123'}
    return FakeYoutubeDL

class TestAndroidBridge(unittest.TestCase):
    def test_mp4_progress_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            listener=Listener()
            path=download_source('https://vt.tiktok.com/ZXabc/', 'mp4', tmp, listener,ytdlp_factory=factory())
            self.assertTrue(Path(path).exists())
            self.assertEqual(listener.events[1],('downloading',50))
    def test_mp3_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=download_source('https://vt.tiktok.com/ZXabc/', 'mp3',tmp,Listener(),ytdlp_factory=factory('m4a'))
            self.assertEqual(Path(path).suffix,'.m4a')
    def test_cancelled(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(UserCancelled):
                download_source('https://vt.tiktok.com/ZXabc/', 'mp4',tmp,Listener(cancel=True),ytdlp_factory=factory())
    def test_invalid_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SocialVaultError):
                download_source('https://vt.tiktok.com.evil.com/a','mp4',tmp,Listener(), ytdlp_factory=factory())
    def test_invalid_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SocialVaultError):
                download_source('https://vt.tiktok.com/ZXabc/','mp5',tmp,Listener(),ytdlp_factory=factory())
    def test_empty_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SocialVaultError):
                download_source('https://vt.tiktok.com/ZXabc/','mp4',tmp,Listener(),ytdlp_factory=factory(content=b''))

if __name__=='__main__': unittest.main()
