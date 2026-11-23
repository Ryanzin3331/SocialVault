"""C2-A/B: real extraction contract simulated without TikTok or network."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app/src/main/python'))
from photo_bridge import inspect_post, PhotoInspectionError, _single_post_url, _photo_url

POST = 'https://www.tiktok.com/@friend/photo/9999000012345'
VIDEO = 'https://www.tiktok.com/@friend/video/9999000012345'
SHORT = 'https://vt.tiktok.com/AbCdfghi/'


def photo_factory(images=3, *, video=False, metadata_changes=False):
    def make(url):
        class Fake:
            def items(self):
                meta = {'id': '9999000012345', 'desc': 'Fotos legais',
                        'post_type': 'video' if video else 'image'}
                yield (2, '', meta)
                if video:
                    yield (3, 'https://cdn.example.org/video.mp4', {'type': 'video'})
                    return
                for i in range(images):
                    # Emulate gallery-dl's mutable post metadata dict.
                    meta.update({'type': 'image', 'num': i + 1,
                                 'width': 1200, 'height': 1600})
                    yield (3, 'https://img.example.org/' + str(i) + '.webp', meta)
        return Fake()
    return make


class PhotoModeTests(unittest.TestCase):
    def test_single_photo(self):
        value = json.loads(inspect_post(POST, extractor_factory=photo_factory(1)))
        self.assertEqual(value['kind'], 'photos')
        self.assertEqual(value['count'], 1)
        self.assertEqual(value['images'][0]['width'], 1200)

    def test_many_photos_are_ordered(self):
        value = json.loads(inspect_post(POST, extractor_factory=photo_factory(10)))
        self.assertEqual([a['index'] for a in value['images']], list(range(1, 11)))
        self.assertEqual(value['images'][9]['url'], 'https://img.example.org/9.webp')

    def test_meta_mutation_does_not_corrupt_order(self):
        value = json.loads(inspect_post(POST, extractor_factory=photo_factory(4, metadata_changes=True)))
        self.assertEqual(value['images'][0]['index'], 1)
        self.assertEqual(value['images'][3]['index'], 4)

    def test_video_detected_no_image(self):
        value = json.loads(inspect_post(VIDEO, extractor_factory=photo_factory(video=True)))
        self.assertEqual(value['kind'], 'video')
        self.assertEqual(value['images'], [])

    def test_url_of_video_can_still_contain_photo_post(self):
        value = json.loads(inspect_post(VIDEO, extractor_factory=photo_factory(2)))
        self.assertEqual(value['kind'], 'photos')

    def test_short_link_queue_follows_only_single_post(self):
        class Queue:
            def items(self):
                yield (6, POST, {'_extractor': object()})
        def factory(url):
            return Queue() if url == SHORT else photo_factory(2)(url)
        value = json.loads(inspect_post(SHORT, extractor_factory=factory))
        self.assertEqual(value['count'], 2)

    def test_short_link_queue_rejects_profile(self):
        class Queue:
            def items(self):
                yield (6, 'https://www.tiktok.com/@friend', {})
        with self.assertRaises(PhotoInspectionError):
            inspect_post(SHORT, extractor_factory=lambda _: Queue())

    def test_short_link_queue_rejects_external_host(self):
        class Queue:
            def items(self):
                yield (6, 'https://evil.example/@friend/photo/123', {})
        with self.assertRaises(PhotoInspectionError):
            inspect_post(SHORT, extractor_factory=lambda _: Queue())

    def test_user_profile_never_traversed(self):
        with self.assertRaises(PhotoInspectionError):
            inspect_post('https://www.tiktok.com/@friend', extractor_factory=photo_factory(2))

    def test_photo_link_supports_share_text(self):
        s = f'Veja o TikTok 👀 {POST}?is_from_webapp=1 mais texto'
        data = json.loads(inspect_post(s, extractor_factory=photo_factory(2)))
        self.assertEqual(data['count'], 2)

    def test_invalid_domain(self):
        with self.assertRaises(Exception):
            inspect_post('https://www.tiktok.com.evil.com/@f/photo/123', extractor_factory=photo_factory())

    def test_missing_extractor(self):
        with self.assertRaises(PhotoInspectionError):
            inspect_post(POST, extractor_factory=lambda url: None)

    def test_large_photo_count_rejected(self):
        with self.assertRaises(PhotoInspectionError):
            inspect_post(POST, extractor_factory=photo_factory(36))

    def test_no_photos_rejected(self):
        with self.assertRaises(PhotoInspectionError):
            inspect_post(POST, extractor_factory=photo_factory(0))

    def test_duplicate_urls_ignored(self):
        class Duplicated:
            def items(self):
                yield (2, '', {'post_type':'image'})
                for _ in range(3):
                    yield (3, 'https://img.example/1.jpg', {'type': 'image'})
        data = json.loads(inspect_post(POST, extractor_factory=lambda url: Duplicated()))
        self.assertEqual(data['count'], 1)

    def test_non_https_media_ignored(self):
        class Invalid:
            def items(self):
                yield (2, '', {'post_type': 'image'})
                yield (3, 'http://cdn.test/1.jpg', {'type': 'image'})
        with self.assertRaises(PhotoInspectionError):
            inspect_post(POST, extractor_factory=lambda url: Invalid())

    def test_single_post_policy(self):
        self.assertEqual(_single_post_url(POST), POST)
        self.assertEqual(_single_post_url(SHORT), SHORT)
        with self.assertRaises(PhotoInspectionError):
            _single_post_url('https://www.tiktok.com/@friend/liked')

    def test_valid_photo_cdn(self):
        self.assertTrue(_photo_url('https://img.example/abc.jpg'))
        self.assertFalse(_photo_url('ftp://img.example/abc.jpg'))

    def test_canonical_short_path(self):
        self.assertEqual(_single_post_url('https://www.tiktok.com/t/ZTest5678/'), 'https://www.tiktok.com/t/ZTest5678/')


if __name__ == '__main__':
    unittest.main()
