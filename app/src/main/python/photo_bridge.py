"""TikTok Photo Mode (C2-A/B): inspect a single post, no bulk crawling.

Only use with public media whose download is permitted by its author.
Photo URLs are returned by gallery-dl's maintained TikTok extractor; this
module never fetches private content, cookies, or login sessions.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

from socialvault.core import normalize_tiktok_url


class PhotoInspectionError(ValueError):
    """Expected user-facing error, including media unavailable/unsupported."""


_POST_RE = re.compile(r"^/(?:@[\w.\-]*/|share/)(?:photo|video)/\d+/?$")
_SHORT_RE = re.compile(r"^/[A-Za-z\d_-]{3,128}/?$")
_MAX_PHOTOS = 35


def _single_post_url(url: str) -> str:
    """Forbid gallery-dl profile/playlist extraction even if input is TikTok."""
    url = normalize_tiktok_url(url)
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if _POST_RE.fullmatch(parts.path):
        return url
    if host in ("vm.tiktok.com", "vt.tiktok.com") and _SHORT_RE.fullmatch(parts.path):
        return url
    if host in ("www.tiktok.com", "tiktok.com") and parts.path.startswith("/t/"):
        if _SHORT_RE.fullmatch(parts.path[2:]):
            return url
    raise PhotoInspectionError("Informe o link de uma única publicação TikTok (vídeo ou fotos).")


def _photo_url(url: object) -> bool:
    if not isinstance(url, str) or not url.startswith("https://") or len(url) > 5000:
        return False
    parsed = urlsplit(url)
    return bool(parsed.hostname) and not parsed.username and not parsed.password


def _sanitize_title(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "Publicação de fotos")).strip()[:140]


def inspect_post(share_text: str, *, extractor_factory=None) -> str:
    """Return JSON {kind:'photos'|'video', images:[{index,url,...}]}.

    `extractor_factory` enables deterministic offline regression tests. For
    short links, gallery-dl emits a Queue message; recursively inspect only
    another validated single-post TikTok URL (max two redirects).
    """
    root_url = _single_post_url(share_text)
    if extractor_factory is None:
        try:
            from gallery_dl import extractor
        except ImportError as exc:
            raise PhotoInspectionError("Motor de fotos indisponível no APK: gallery-dl ausente.") from exc
        extractor_factory = extractor.find

    visited = set()
    image_urls = set()
    images: list[dict] = []
    kind = None
    post_id = ""
    title = "Publicação de fotos"

    def inspect_one(url: str, depth: int) -> None:
        nonlocal kind, post_id, title
        if depth > 2 or url in visited:
            raise PhotoInspectionError("Redirecionamento inesperado da publicação.")
        visited.add(url)
        handler = extractor_factory(url)
        if handler is None:
            raise PhotoInspectionError("O formato desse link ainda não é reconhecido.")

        for message in handler.items():
            code = message[0]
            if code == 6:  # gallery_dl.extractor.message.Message.Queue
                # A short URL leads to the canonical URL. Never follow
                # a queue to a user profile or a different website.
                next_url = _single_post_url(str(message[1]))
                inspect_one(next_url, depth + 1)
            elif code == 2:  # Message.Directory
                meta = message[2]
                if isinstance(meta, dict):
                    kind = meta.get("post_type") or kind
                    post_id = str(meta.get("id") or post_id)[:60]
                    title = _sanitize_title(meta.get("desc") or title)
            elif code == 3:  # Message.Url
                url_item, meta = message[1], message[2]
                if not isinstance(meta, dict) or meta.get("type") != "image":
                    continue
                if not _photo_url(url_item) or url_item in image_urls:
                    continue
                if len(images) >= _MAX_PHOTOS:
                    raise PhotoInspectionError("A publicação excede o limite de 35 imagens desta versão.")
                image_urls.add(url_item)
                images.append({
                    "index": len(images) + 1,
                    "url": url_item,
                    "width": int(meta.get("width") or 0),
                    "height": int(meta.get("height") or 0),
                })
                kind = "image"
                post_id = str(meta.get("id") or post_id)[:60]
                title = _sanitize_title(meta.get("desc") or title)

    try:
        inspect_one(root_url, 0)
    except PhotoInspectionError:
        raise
    except Exception as exc:
        raise PhotoInspectionError(
            "Não foi possível consultar as fotos. Publicação indisponível ou TikTok alterou o acesso."
        ) from exc

    if images:
        return json.dumps({
            "kind": "photos", "post_id": post_id, "title": title,
            "count": len(images), "images": images,
        }, ensure_ascii=False)
    if kind == "video":
        return json.dumps({"kind": "video", "post_id": post_id, "images": []}, ensure_ascii=False)
    raise PhotoInspectionError("Não foram encontradas fotos acessíveis nessa publicação.")
