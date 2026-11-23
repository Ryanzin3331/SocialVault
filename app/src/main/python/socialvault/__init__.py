"""SocialVault: motor local e reutilizável para mídia autorizada do TikTok."""

from .core import DownloadResult, DownloadProgress, SocialVaultError, download, inspect, normalize_tiktok_url

__all__ = [
    "DownloadResult", "DownloadProgress", "SocialVaultError",
    "download", "inspect", "normalize_tiktok_url",
]
__version__ = "0.1.0-alpha"
