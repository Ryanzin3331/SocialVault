"""Adaptador Android para o motor Python Fase A.

A biblioteca yt-dlp é a dependência externa, incorporada ao APK pelo Chaquopy.
FFmpeg/MediaStore são executados via Java; Python nunca acessa armazenamento
compartilhado nem precisa executar binários no shell do Android.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from socialvault.core import normalize_tiktok_url, SocialVaultError


class UserCancelled(Exception):
    pass


def download_source(
    share_text: str, mode: str, directory: str, listener: Any,
    *, ytdlp_factory: Callable[..., Any] | None = None,
) -> str:
    """Baixa uma fonte para cache privado. Retorna caminho absoluto.

    MP4 seleciona um arquivo progressivo MP4 com áudio, para não depender de
    subprocessos FFmpeg que não existem no Chaquopy.
    MP3 baixa a melhor fonte de áudio; Java converte depois com FFmpegKit.
    """
    url = normalize_tiktok_url(share_text)
    if mode not in ("mp4", "mp3"):
        raise SocialVaultError("Formato inválido.")
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise SocialVaultError("O cache desta tarefa não está vazio.")

    if ytdlp_factory is None:
        from yt_dlp import YoutubeDL
        ytdlp_factory = YoutubeDL

    def hook(event: dict) -> None:
        if listener.isCancelled():
            raise UserCancelled("Download cancelado.")
        if event.get("status") == "downloading":
            done = event.get("downloaded_bytes") or 0
            total = event.get("total_bytes") or event.get("total_bytes_estimate") or 0
            progress = int(done * 100 / total) if total else -1
            listener.onProgress("downloading", max(-1, min(100, progress)))
        elif event.get("status") == "finished":
            listener.onProgress("processing", 100)

    opts = {
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "retries": 3, "fragment_retries": 3, "socket_timeout": 20,
        "restrictfilenames": True,
        "outtmpl": str(root / "%(id)s.%(ext)s"),
        "progress_hooks": [hook],
        # Somente arquivos progressivos MP4. Fluxos separados exigem
        # remuxing externo, que entra no módulo de qualidade avançada.
        "format": "best[ext=mp4]" if mode == "mp4" else "bestaudio/best",
    }
    try:
        listener.onProgress("starting", 0)
        with ytdlp_factory(opts) as ydl:
            info = ydl.extract_info(url, download=True)
        if listener.isCancelled():
            raise UserCancelled("Download cancelado.")
    except UserCancelled:
        raise
    except Exception as exc:
        if listener.isCancelled():
            raise UserCancelled("Download cancelado.") from exc
        raise SocialVaultError(f"O TikTok não disponibilizou a mídia: {exc}") from exc

    if isinstance(info, dict) and (info.get("entries") is not None or info.get("_type") == "playlist"):
        raise SocialVaultError("Somente links de vídeos individuais são aceitos.")

    results = [p for p in root.iterdir() if p.is_file() and not p.name.endswith((".part", ".ytdl", ".temp"))]
    results = [p for p in results if p.suffix.lower() in ((".mp4",) if mode == "mp4" else (".m4a", ".webm", ".mp3", ".opus", ".mp4", ".ogg"))]
    if len(results) != 1 or results[0].stat().st_size <= 0:
        raise SocialVaultError("O arquivo final não foi encontrado ou está vazio.")
    return str(results[0].resolve())
