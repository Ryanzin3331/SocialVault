"""Phase C1 contracts: selectable resolutions, download artifacts and regressions.
No network access or TikTok requests are made by these tests.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app' / 'src' / 'main' / 'python'))
from android_bridge import _video_formats, inspect_qualities, download_media_source, UserCancelled
from socialvault.core import SocialVaultError

URL = 'https://www.tiktok.com/@test/video/1234'
FORMATS = [
    {'format_id':'p360', 'ext':'mp4', 'height':360, 'vcodec':'h264', 'acodec':'aac', 'tbr':350},
    {'format_id':'p720', 'ext':'mp4', 'height':720, 'vcodec':'h264', 'acodec':'aac', 'tbr':1450},
    {'format_id':'v1080', 'ext':'mp4', 'height':1080, 'vcodec':'h264', 'acodec':'none', 'tbr':3200},
    {'format_id':'a256', 'ext':'m4a', 'vcodec':'none', 'acodec':'aac', 'abr':256},
    {'format_id':'webm2160', 'ext':'webm', 'height':2160, 'vcodec':'vp9', 'acodec':'none'},
]


class Listener:
    def __init__(self, cancelled=False):
        self.cancelled = cancelled
        self.events = []
    def isCancelled(self): return self.cancelled
    def onProgress(self, stage, pct): self.events.append(('progress',stage,pct))
    def onTransfer(self, stage, pct, done, total, speed, eta):
        self.events.append(('transfer',stage,pct,done,total,speed,eta))


class FakeDL:
    downloads = []
    fail_at = None
    metadata = {'title': 'Exemplo', 'formats':FORMATS}
    def __init__(self, opts): self.opts = opts
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def extract_info(self, url, download=False):
        if not download: return self.metadata
        format_id = self.opts['format']
        self.downloads.append(format_id)
        if format_id == self.fail_at: raise RuntimeError('Simulated network error')
        fmt = next((f for f in self.metadata['formats'] if f['format_id']==format_id), None)
        if fmt is None and format_id == 'bestaudio/best':
            fmt = {'ext':'m4a'}
        if fmt is None: raise ValueError(f'Unexpected format: {format_id}')
        destination = Path(self.opts['outtmpl'].replace('%(ext)s', fmt['ext']))
        self.opts['progress_hooks'][0]({'status':'downloading', 'downloaded_bytes':512, 'total_bytes':1024, 'speed':8000, 'eta':1})
        destination.write_bytes(b'fake media payload')
        self.opts['progress_hooks'][0]({'status':'finished'})
        return self.metadata


class QualityTests(unittest.TestCase):
    def setUp(self):
        FakeDL.downloads = []
        FakeDL.fail_at = None
        FakeDL.metadata = {'title':'Exemplo', 'formats':FORMATS}

    def test_height_order_and_split(self):
        result = json.loads(inspect_qualities(URL, ytdlp_factory=FakeDL))
        self.assertEqual(result['heights'], [1080,720,360])
        self.assertEqual(result['split_heights'], [1080])

    def test_portrait_1080_x_1920_reports_1080p(self):
        formats = [
            {'format_id':'portrait', 'width':1080, 'height':1920,
             'ext':'mp4', 'vcodec':'h264', 'acodec':'aac'},
            {'format_id':'low', 'width':540, 'height':960,
             'ext':'mp4', 'vcodec':'h264', 'acodec':'aac'},
        ]
        self.assertEqual([f['height'] for f in _video_formats({'formats':formats})], [1080,540])

    def test_direct_at_requested_height(self):
        with tempfile.TemporaryDirectory() as tmp:
            listener = Listener()
            result = json.loads(download_media_source(URL,'mp4',tmp,listener,720,ytdlp_factory=FakeDL))
            self.assertEqual(FakeDL.downloads, ['p720'])
            self.assertFalse(result['merge'])
            self.assertEqual(result['height'], 720)
            self.assertTrue(Path(result['video']).is_file())
            self.assertTrue(any(e[0]=='transfer' and e[5]==8000 for e in listener.events))

    def test_best_automatic_uses_max_height(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = json.loads(download_media_source(URL,'mp4',tmp,Listener(),0,ytdlp_factory=FakeDL))
            self.assertEqual(FakeDL.downloads, ['v1080','a256'])
            self.assertTrue(result['merge'])
            self.assertTrue(Path(result['audio']).is_file())

    def test_quality_not_offered_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(SocialVaultError,'Qualidade indisponível'):
                download_media_source(URL,'mp4',tmp,Listener(),480,ytdlp_factory=FakeDL)
            self.assertEqual(FakeDL.downloads, [])

    def test_mp3_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = json.loads(download_media_source(URL,'mp3',tmp,Listener(),0,ytdlp_factory=FakeDL))
            self.assertEqual(FakeDL.downloads, ['bestaudio/best'])
            self.assertEqual(Path(result['video']).suffix,'.m4a')
            self.assertFalse(result['merge'])

    def test_cancel_before_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(UserCancelled):
                download_media_source(URL,'mp4',tmp,Listener(True),0,ytdlp_factory=FakeDL)
            self.assertFalse(FakeDL.downloads)

    def test_failed_audio_does_not_return_partial(self):
        FakeDL.fail_at='a256'
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SocialVaultError):
                download_media_source(URL,'mp4',tmp,Listener(),1080,ytdlp_factory=FakeDL)
            self.assertEqual(FakeDL.downloads,['v1080','a256'])

    def test_no_audio_excludes_split(self):
        result = _video_formats({'formats':[f for f in FORMATS if f['format_id'] != 'a256']})
        self.assertEqual([x['height'] for x in result],[720,360])

    def test_invalid_source_and_negative_height(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SocialVaultError):
                inspect_qualities('https://fake.tiktok.com.evil.com/video/abc', ytdlp_factory=FakeDL)
            with self.assertRaises(SocialVaultError):
                download_media_source(URL,'mp4',tmp,Listener(),-1,ytdlp_factory=FakeDL)

    def test_playlist_rejected(self):
        FakeDL.metadata = {'entries':[{'id':'1'}], 'formats':FORMATS}
        with self.assertRaises(SocialVaultError):
            inspect_qualities(URL, ytdlp_factory=FakeDL)


if __name__=='__main__': unittest.main()
