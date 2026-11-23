import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from socialvault.core import (
    SocialVaultError, _format_for_mp4, _make_options,
    download, inspect, normalize_tiktok_url,
)

LINK = "https://www.tiktok.com/@exemplo/video/1234567890123456789"


class FakeYoutubeDL:
    """Simula as respostas da biblioteca sem acessar a internet."""

    def __init__(self, options, *, fail=False, create_file=True):
        self.options = options
        self.fail = fail
        self.create_file = create_file

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def extract_info(self, url, *, download):
        if self.fail:
            raise RuntimeError("erro de rede simulado")
        info = {
            "title": "Som engraçado!", "uploader": "criador_teste",
            "width": 1080, "height": 1920, "id": "12345",
            "formats": [{"height": 1080}, {"height": 720}],
        }
        if download and self.create_file:
            ext = "mp3" if "postprocessors" in self.options else "mp4"
            target = Path(self.options["outtmpl"]).parent / f"Som engraçado [12345].{ext}"
            target.write_bytes(b"conteudo-simulado-nao-e-uma-midia-real")
            for hook in self.options.get("progress_hooks", []):
                hook({"status": "downloading", "downloaded_bytes": 500, "total_bytes": 1000, "speed": 12345, "eta": 2})
                hook({"status": "finished"})
        return info


def factory(**kwargs):
    return lambda opts: FakeYoutubeDL(opts, **kwargs)


class TestURL(unittest.TestCase):
    def test_url_direta(self):
        self.assertEqual(normalize_tiktok_url(LINK), LINK)

    def test_url_de_texto_compartilhado(self):
        share = "Gostei! https://vt.tiktok.com/ZSalGumaCoisa/ Assista no TikTok"
        self.assertEqual(normalize_tiktok_url(share), "https://vt.tiktok.com/ZSalGumaCoisa/")

    def test_rejeita_dominios_maliciosos(self):
        for url in (
            "https://tiktok.com.malicioso.com/@u/video/2",
            "https://tiktok.com@servidor-malicioso.com/abc",
            "https://example.org/video/222",
            "https://www.tiktok.com/",
            "http://www.tiktok.com:8080/abc",
        ):
            with self.subTest(url=url), self.assertRaises(SocialVaultError):
                normalize_tiktok_url(url)

    def test_escolhe_url_do_tiktok_no_meio_do_texto(self):
        s = "Visite https://example.org/link. Depois https://vm.tiktok.com/ZSA1234/."
        self.assertEqual(normalize_tiktok_url(s), "https://vm.tiktok.com/ZSA1234/")


class TestFormat(unittest.TestCase):
    def test_separados_quando_ffmpeg_presente(self):
        self.assertIn("bv[ext=mp4]+ba[ext=m4a]", _format_for_mp4(True))

    def test_sem_ffmpeg_requer_video_progressivo_mp4(self):
        self.assertEqual(_format_for_mp4(False), "b[ext=mp4]")

    def test_mp3_configura_ffmpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            options = _make_options(mode="mp3", work_dir=Path(tmp), emit=lambda _: None, has_ffmpeg=True)
            pp = options["postprocessors"][0]
            self.assertEqual(pp["key"], "FFmpegExtractAudio")
            self.assertEqual(pp["preferredcodec"], "mp3")
            self.assertEqual(pp["preferredquality"], "192")


class TestDownload(unittest.TestCase):
    def test_mp4_resultado_e_progresso(self):
        events = []
        with tempfile.TemporaryDirectory() as tmp, patch("socialvault.core._ffmpeg_available", return_value=True):
            result = download(LINK, mode="mp4", output_dir=tmp, progress_callback=events.append,
                              ytdlp_factory=factory())
            self.assertTrue(result.path.is_file())
            self.assertEqual(result.path.suffix, ".mp4")
            self.assertEqual(result.title, "Som engraçado!")
            self.assertEqual(result.height, 1920)
            self.assertEqual([e.stage for e in events], ["starting", "downloading", "processing", "saving", "done"])
            self.assertAlmostEqual(events[1].percent, 50.0)
            self.assertEqual(len(list(Path(tmp).iterdir())), 1)  # Temporários limpos

    def test_preserva_arquivo_ao_baixar_duas_vezes(self):
        with tempfile.TemporaryDirectory() as tmp, patch("socialvault.core._ffmpeg_available", return_value=False):
            a = download(LINK, output_dir=tmp, ytdlp_factory=factory())
            b = download(LINK, output_dir=tmp, ytdlp_factory=factory())
            self.assertNotEqual(a.path, b.path)
            self.assertEqual(a.path.read_bytes(), b.path.read_bytes())

    def test_mp3_com_ffmpeg(self):
        with tempfile.TemporaryDirectory() as tmp, patch("socialvault.core._ffmpeg_available", return_value=True):
            result = download(LINK, mode="mp3", output_dir=tmp, ytdlp_factory=factory())
            self.assertEqual(result.path.suffix, ".mp3")

    def test_mp3_exige_ffmpeg(self):
        with tempfile.TemporaryDirectory() as tmp, patch("socialvault.core._ffmpeg_available", return_value=False):
            with self.assertRaisesRegex(SocialVaultError, "FFmpeg"):
                download(LINK, mode="mp3", output_dir=tmp, ytdlp_factory=factory())

    def test_erro_de_rede_limpa_temporarios(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(SocialVaultError, "Falha no download"):
                download(LINK, output_dir=tmp, ytdlp_factory=factory(fail=True))
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_sem_arquivo_nao_gera_sucesso_falso(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(SocialVaultError, "encontrei 0"):
                download(LINK, output_dir=tmp, ytdlp_factory=factory(create_file=False))
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_modo_invalido(self):
        with self.assertRaisesRegex(SocialVaultError, "Modo inválido"):
            download(LINK, mode="wav", ytdlp_factory=factory())


class TestInspect(unittest.TestCase):
    def test_inspect_nao_cria_arquivo(self):
        info = inspect(LINK, ytdlp_factory=factory())
        self.assertEqual(info["available_heights"], [1080, 720])
        self.assertEqual(info["creator"], "criador_teste")


if __name__ == "__main__":
    unittest.main()
