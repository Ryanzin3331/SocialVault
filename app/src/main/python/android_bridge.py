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

# Phase C1: quality inspection and selection (MP4 progressive or native-stream remux).
# No video re-encoding takes place. This module never invokes an external
# executable from the Chaquopy process: Android uses its embedded FFmpegKit.
import json


def _video_formats(info: dict) -> list[dict]:
    """MP4-compatible formats, ordered by height, with progressive preferred.

    A higher resolution available only as a video-only stream is offered if a
    compatible audio stream exists to merge later in the Android layer.
    """
    formats = [f for f in (info.get('formats') or []) if isinstance(f, dict)]
    audio_formats = [f for f in formats if f.get('format_id') and
                     f.get('vcodec') == 'none' and
                     f.get('acodec') not in (None, 'none') and
                     f.get('ext') in ('m4a', 'mp4')]
    audio = max(audio_formats, key=lambda f: (f.get('abr') or f.get('tbr') or 0,
                                               f.get('filesize') or 0), default=None)
    candidates = {}
    for f in formats:
        height = f.get('height')
        width = f.get('width')
        # Portrait TikTok 1080x1920 must appear as 1080p, not 1920p.
        if isinstance(width, int) and width > 0 and isinstance(height, int) and height > 0:
            height = min(width, height)
        if not isinstance(height, int) or height <= 0 or not f.get('format_id'):
            continue
        if f.get('ext') != 'mp4' or f.get('vcodec') in (None, 'none'):
            continue
        progressive = f.get('acodec') not in (None, 'none')
        if not progressive and audio is None:
            continue
        # The direct MP4 avoids an additional transfer and remux at equal height.
        score = (1 if progressive else 0, f.get('tbr') or 0, f.get('filesize') or 0)
        previous = candidates.get(height)
        if previous is None or score > previous[0]:
            candidates[height] = (score, f, None if progressive else audio)
    return [dict(height=h, video=data[1], audio=data[2])
            for h, data in sorted(candidates.items(), reverse=True)]


def inspect_qualities(share_text: str, *, ytdlp_factory=None) -> str:
    """Return a JSON list of MP4 resolutions genuinely offered to this client.

    The UI calls this only on explicit user request to avoid an unnecessary
    network request for fast one-tap downloads.
    """
    url = normalize_tiktok_url(share_text)
    if ytdlp_factory is None:
        from yt_dlp import YoutubeDL
        ytdlp_factory = YoutubeDL
    try:
        with ytdlp_factory({'quiet': True, 'no_warnings': True,
                            'noplaylist': True, 'skip_download': True,
                            'socket_timeout': 15}) as ydl:
            info = ydl.extract_info(url, download=False)
        if not isinstance(info, dict) or info.get('entries') is not None:
            raise SocialVaultError('Apenas vídeos individuais são compatíveis.')
        selected = _video_formats(info)
        return json.dumps({'heights': [entry['height'] for entry in selected],
                           'split_heights': [entry['height'] for entry in selected if entry['audio']],
                           'title': str(info.get('title') or '')[:120]})
    except SocialVaultError:
        raise
    except Exception as exc:
        raise SocialVaultError(f'Não foi possível consultar as qualidades: {exc}') from exc


def download_media_source(share_text: str, mode: str, directory: str,
                          listener: Any, quality_height: int = 0,
                          *, ytdlp_factory=None) -> str:
    """Download sources and return a JSON envelope understood by Android Java.

    The selected height must be one of the exact MP4 resolutions reported by
    the extractor. When split, the Android layer joins streams with stream copy.
    """
    url = normalize_tiktok_url(share_text)
    if mode not in ('mp4', 'mp3'):
        raise SocialVaultError('Formato inválido.')
    if not isinstance(quality_height, int) or quality_height < 0:
        raise SocialVaultError('Qualidade inválida.')
    if listener.isCancelled():
        raise UserCancelled('Download cancelado.')
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise SocialVaultError('O cache desta tarefa não está vazio.')
    if ytdlp_factory is None:
        from yt_dlp import YoutubeDL
        ytdlp_factory = YoutubeDL

    def emit_hook(stage):
        def hook(event):
            if listener.isCancelled():
                raise UserCancelled('Download cancelado.')
            if event.get('status') == 'downloading':
                received = int(event.get('downloaded_bytes') or 0)
                total = int(event.get('total_bytes') or event.get('total_bytes_estimate') or 0)
                percent = max(0, min(100, int(100 * received / total))) if total else -1
                speed = int(event.get('speed') or 0)
                eta = int(event.get('eta') or -1)
                if hasattr(listener, 'onTransfer'):
                    listener.onTransfer(stage, percent, received, total, speed, eta)
                else:
                    listener.onProgress('downloading', percent)
            elif event.get('status') == 'finished':
                listener.onProgress('processing', 100)
        return hook

    def get_file(prefix, valid_exts):
        matches = [p for p in root.glob(prefix + '.*')
                   if p.is_file() and p.suffix.lower() in valid_exts and p.stat().st_size > 0]
        if len(matches) != 1:
            raise SocialVaultError('Arquivo de mídia ausente ou vazio após o download.')
        return matches[0]

    def fetch_format(fmt_id: str, prefix: str, stage: str):
        if listener.isCancelled():
            raise UserCancelled('Download cancelado.')
        opts = {'quiet': True, 'no_warnings': True, 'noplaylist': True,
                'retries': 3, 'fragment_retries': 3, 'socket_timeout': 20,
                'continuedl': True, 'buffersize': 128 * 1024,
                'concurrent_fragment_downloads': 3,
                'format': str(fmt_id), 'outtmpl': str(root / (prefix + '.%(ext)s')),
                'progress_hooks': [emit_hook(stage)]}
        with ytdlp_factory(opts) as ydl:
            ydl.extract_info(url, download=True)

    try:
        listener.onProgress('starting', 0)
        if mode == 'mp3':
            # Existing, proven audio selector is preserved for reliability.
            opts = {'quiet': True, 'no_warnings': True, 'noplaylist': True,
                    'retries': 3, 'fragment_retries': 3, 'socket_timeout': 20,
                    'continuedl': True, 'buffersize': 128 * 1024,
                    'concurrent_fragment_downloads': 3,
                    'format': 'bestaudio/best',
                    'outtmpl': str(root / 'audio.%(ext)s'),
                    'progress_hooks': [emit_hook('audio')]}
            with ytdlp_factory(opts) as ydl:
                ydl.extract_info(url, download=True)
            audio = get_file('audio', ('.m4a', '.webm', '.mp3', '.opus', '.mp4', '.ogg'))
            return json.dumps({'video': str(audio.resolve()), 'audio': None, 'merge': False})

        # Auto selects highest available MP4 height, not just progressive MP4.
        # Only one metadata query; the selected stream is downloaded by ID.
        with ytdlp_factory({'quiet': True, 'no_warnings': True,
                            'noplaylist': True, 'skip_download': True,
                            'socket_timeout': 15}) as ydl:
            info = ydl.extract_info(url, download=False)
        if not isinstance(info, dict) or info.get('entries') is not None:
            raise SocialVaultError('Apenas vídeos individuais são compatíveis.')
        choices = _video_formats(info)
        if not choices:
            # Older TikTok results sometimes omit complete formats metadata.
            # The legacy progressive selector still provides a safe fallback.
            if quality_height:
                raise SocialVaultError('Esta resolução não está disponível.')
            path = download_source(url, 'mp4', directory, listener, ytdlp_factory=ytdlp_factory)
            return json.dumps({'video': path, 'audio': None, 'merge': False})
        chosen = next((c for c in choices if c['height'] == quality_height), None) if quality_height else choices[0]
        if chosen is None:
            raise SocialVaultError('Qualidade indisponível neste vídeo. Consulte novamente.')
        fetch_format(chosen['video']['format_id'], 'video', 'video')
        video = get_file('video', ('.mp4',))
        if chosen['audio']:
            fetch_format(chosen['audio']['format_id'], 'audio', 'audio')
            audio = get_file('audio', ('.m4a', '.mp4'))
            return json.dumps({'video': str(video.resolve()),
                               'audio': str(audio.resolve()), 'merge': True,
                               'height': chosen['height']})
        return json.dumps({'video': str(video.resolve()), 'audio': None,
                           'merge': False, 'height': chosen['height']})
    except UserCancelled:
        raise
    except SocialVaultError:
        raise
    except Exception as exc:
        if listener.isCancelled():
            raise UserCancelled('Download cancelado.') from exc
        raise SocialVaultError(f'O TikTok não disponibilizou a mídia: {exc}') from exc
