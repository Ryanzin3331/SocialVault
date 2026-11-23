"""Motor de download desacoplado de interface, sistema operacional e biblioteca externa.

Usar apenas para mídias cujo download/reutilização seja autorizado. O TikTok
nem sempre expõe essa permissão em metadados consultáveis por terceiros; este
projeto não afirma conseguir verificá-la programaticamente.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal
from urllib.parse import urlsplit

Mode = Literal["mp4", "mp3"]
ProgressCallback = Callable[["DownloadProgress"], None]

_ALLOWED_HOSTS = frozenset({
    "tiktok.com", "www.tiktok.com", "m.tiktok.com",
    "vm.tiktok.com", "vt.tiktok.com",
})
_URL_RE = re.compile(r"https?://[^\s<>\"'`]+", re.IGNORECASE)


class SocialVaultError(Exception):
    """Erro apresentável na interface/CLI (sem traceback técnico obrigatório)."""


@dataclass(frozen=True)
class DownloadProgress:
    stage: str
    percent: float | None = None
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    speed_bytes_per_sec: float | None = None
    eta_seconds: int | None = None


@dataclass(frozen=True)
class DownloadResult:
    path: Path
    mode: Mode
    title: str
    creator: str | None
    source_url: str
    size_bytes: int
    width: int | None
    height: int | None


def normalize_tiktok_url(text: str) -> str:
    """Aceita URL direta ou texto copiado do menu Compartilhar do TikTok.

    Não segue redirects aqui, portanto só aceita hosts oficiais do TikTok.
    """
    if not isinstance(text, str) or not text.strip():
        raise SocialVaultError("Cole ou compartilhe um link do TikTok.")

    for match in _URL_RE.finditer(text.strip()):
        url = match.group(0).rstrip(".,;:!?)\u3002\uff0c")
        parts = urlsplit(url)
        if parts.scheme.lower() not in ("http", "https"):
            continue
        if parts.username or parts.password:
            continue
        if (parts.hostname or "").lower() not in _ALLOWED_HOSTS:
            continue
        try:
            if parts.port not in (None, 80, 443):
                continue
        except ValueError:
            continue
        if not parts.path or parts.path == "/":
            continue
        return url

    raise SocialVaultError(
        "Link inválido: por enquanto, só são aceitos links oficiais do TikTok."
    )


def default_output_dir() -> Path:
    """Detecta armazenamento compartilhado já liberado no Termux, se disponível."""
    termux_downloads = Path.home() / "storage" / "downloads"
    base = termux_downloads if termux_downloads.is_dir() else Path.home() / "Downloads"
    return base / "SocialVault"


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _format_for_mp4(has_ffmpeg: bool) -> str:
    # Prioridade a vídeo H.264/MP4 + áudio M4A sem reencode, e em seguida MP4
    # progressivo. Sem FFmpeg, evitar streams separados que exigem fusão.
    return (
        "bv[ext=mp4]+ba[ext=m4a]/b[ext=mp4]"
        if has_ffmpeg else "b[ext=mp4]"
    )


def _make_options(
    *, mode: Mode, work_dir: Path, emit: ProgressCallback,
    has_ffmpeg: bool,
) -> dict[str, Any]:
    def hook(data: dict[str, Any]) -> None:
        status = data.get("status")
        if status == "downloading":
            received = data.get("downloaded_bytes")
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            percent = (
                max(0.0, min(100.0, received * 100.0 / total))
                if isinstance(received, (int, float)) and isinstance(total, (int, float)) and total > 0
                else None
            )
            emit(DownloadProgress(
                stage="downloading", percent=percent,
                downloaded_bytes=received if isinstance(received, int) else None,
                total_bytes=total if isinstance(total, int) else None,
                speed_bytes_per_sec=data.get("speed"),
                eta_seconds=data.get("eta"),
            ))
        elif status == "finished":
            emit(DownloadProgress(stage="processing"))

    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": False,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 15,
        "restrictfilenames": False,
        "outtmpl": str(work_dir / "%(uploader).40s - %(title).80s [%(id)s].%(ext)s"),
        "progress_hooks": [hook],
    }
    if mode == "mp4":
        opts["format"] = _format_for_mp4(has_ffmpeg)
        if has_ffmpeg:
            opts["merge_output_format"] = "mp4"
    else:
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    return opts


def _make_inspect_options() -> dict[str, Any]:
    return {
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "skip_download": True, "socket_timeout": 15,
    }


def _extract_single_metadata(info: Any) -> dict[str, Any]:
    if not isinstance(info, dict):
        raise SocialVaultError("A plataforma não retornou dados válidos do vídeo.")
    # Não escolher vídeos de playlists arbitrárias; a Fase A só trata um link.
    if info.get("_type") in ("playlist", "multi_video") or info.get("entries") is not None:
        raise SocialVaultError("Esta versão só aceita um vídeo por vez.")
    return info


def _load_ytdlp_factory() -> Callable[..., Any]:
    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise SocialVaultError(
            "Dependência ausente: instale com 'python -m pip install -r requirements.txt'."
        ) from exc
    return YoutubeDL


def inspect(url_or_share_text: str, *, ytdlp_factory: Callable[..., Any] | None = None) -> dict[str, Any]:
    """Consulta título, criador e formatos sem baixar arquivos de mídia."""
    url = normalize_tiktok_url(url_or_share_text)
    factory = ytdlp_factory or _load_ytdlp_factory()
    try:
        with factory(_make_inspect_options()) as client:
            info = _extract_single_metadata(client.extract_info(url, download=False))
    except SocialVaultError:
        raise
    except Exception as exc:
        raise SocialVaultError(f"Não foi possível consultar o vídeo: {exc}") from exc
    formats = info.get("formats") or []
    heights = sorted({
        f["height"] for f in formats
        if isinstance(f, dict) and isinstance(f.get("height"), int) and f["height"] > 0
    }, reverse=True)
    if not heights and isinstance(info.get("height"), int):
        heights = [info["height"]]
    return {
        "title": str(info.get("title") or "Vídeo sem título"),
        "creator": info.get("uploader") or info.get("channel"),
        "available_heights": heights,
        "source_url": url,
        "note": "Resoluções reportadas pela plataforma; disponibilidade pode mudar no download.",
    }


def _publish_file(source: Path, output_dir: Path) -> Path:
    """Publica um arquivo completo, sem sobrescrever downloads anteriores.

    Usa hard link para publicação sem clobber no mesmo sistema de arquivos.
    Na ausência de suporte a hard links, usa criação exclusiva e cópia.
    """
    if not source.is_file():
        raise SocialVaultError("O arquivo final não foi encontrado após o processamento.")
    base = source.stem
    suffix = source.suffix.lower()
    for index in range(1, 1001):
        filename = f"{base}{f' ({index})' if index > 1 else ''}{suffix}"
        destination = output_dir / filename
        try:
            os.link(source, destination)
            return destination
        except FileExistsError:
            continue
        except (OSError, NotImplementedError):
            # Windows/Android: fallback sem sobrescrever nomes já existentes.
            try:
                with destination.open("xb") as target, source.open("rb") as original:
                    shutil.copyfileobj(original, target, length=1024 * 1024)
                return destination
            except FileExistsError:
                continue
            except OSError:
                destination.unlink(missing_ok=True)
                raise
    raise SocialVaultError("Muitos arquivos com o mesmo nome na pasta de destino.")


def download(
    url_or_share_text: str,
    *,
    mode: Mode = "mp4",
    output_dir: str | Path | None = None,
    progress_callback: ProgressCallback | None = None,
    ytdlp_factory: Callable[..., Any] | None = None,
) -> DownloadResult:
    """Baixa vídeo MP4 ou extrai MP3, com diretório temporário isolado.

    Esta função é síncrona. No futuro aplicativo, execute em worker e envie
    os eventos de progresso à interface, nunca na thread principal Android.
    """
    url = normalize_tiktok_url(url_or_share_text)
    if mode not in ("mp4", "mp3"):
        raise SocialVaultError("Modo inválido. Escolha 'mp4' ou 'mp3'.")
    if mode == "mp3" and not _ffmpeg_available():
        raise SocialVaultError("Para MP3, instale FFmpeg e FFprobe e coloque-os no PATH.")

    out = Path(output_dir).expanduser() if output_dir is not None else default_output_dir()
    try:
        out.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SocialVaultError(f"Não foi possível criar a pasta de destino: {exc}") from exc

    factory = ytdlp_factory or _load_ytdlp_factory()
    emit = progress_callback or (lambda _: None)
    has_ffmpeg = _ffmpeg_available()

    try:
        emit(DownloadProgress(stage="starting"))
        with tempfile.TemporaryDirectory(prefix=".socialvault-", dir=out) as tmp:
            work_dir = Path(tmp)
            opts = _make_options(mode=mode, work_dir=work_dir, emit=emit, has_ffmpeg=has_ffmpeg)
            try:
                with factory(opts) as client:
                    info = _extract_single_metadata(client.extract_info(url, download=True))
            except SocialVaultError:
                raise
            except Exception as exc:
                raise SocialVaultError(f"Falha no download: {exc}") from exc

            matching = sorted(
                (p for p in work_dir.iterdir() if p.is_file() and p.suffix.lower() == f".{mode}"),
                key=lambda p: p.stat().st_size,
                reverse=True,
            )
            if len(matching) != 1:
                raise SocialVaultError(
                    f"Esperava exatamente um arquivo {mode.upper()} final, "
                    f"mas encontrei {len(matching)}. Nenhum arquivo foi publicado."
                )
            emit(DownloadProgress(stage="saving"))
            published = _publish_file(matching[0], out)
            result = DownloadResult(
                path=published,
                mode=mode,
                title=str(info.get("title") or published.stem),
                creator=info.get("uploader") or info.get("channel"),
                source_url=url,
                size_bytes=published.stat().st_size,
                width=info.get("width") if isinstance(info.get("width"), int) else None,
                height=info.get("height") if isinstance(info.get("height"), int) else None,
            )
        emit(DownloadProgress(stage="done", percent=100.0, downloaded_bytes=result.size_bytes,
                              total_bytes=result.size_bytes))
        return result
    except SocialVaultError:
        raise
    except OSError as exc:
        raise SocialVaultError(f"Erro ao salvar o arquivo: {exc}") from exc
