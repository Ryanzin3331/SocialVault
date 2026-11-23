"""CLI simples para validar o motor no Windows/Linux/Termux."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import SocialVaultError, default_output_dir, download, inspect


def _read_url(args_url: str | None) -> str:
    if args_url:
        return args_url
    print("Cole o link ou texto compartilhado pelo TikTok:")
    return input("> ")


def _print_progress(p):
    if p.stage == "downloading":
        pct = f"{p.percent:5.1f}%" if p.percent is not None else "  --  "
        speed = f"{p.speed_bytes_per_sec / 1024 / 1024:.2f} MiB/s" if p.speed_bytes_per_sec else "-- MiB/s"
        eta = f"ETA {p.eta_seconds}s" if p.eta_seconds is not None else "ETA --"
        print(f"\rBaixando: {pct} | {speed} | {eta}       ", end="", flush=True)
    elif p.stage == "processing":
        print("\nProcessando mídia...", flush=True)
    elif p.stage == "saving":
        print("Salvando arquivo final...", flush=True)
    elif p.stage == "done":
        print("Concluído!", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="socialvault",
        description="Motor local para mídia do TikTok com download autorizado.",
    )
    subs = parser.add_subparsers(dest="command", required=True)
    p_down = subs.add_parser("download", help="Baixar vídeo MP4 ou extrair MP3")
    p_down.add_argument("url", nargs="?", help="URL ou texto de compartilhamento do TikTok")
    p_down.add_argument("--mode", choices=["mp4", "mp3"], default="mp4")
    p_down.add_argument("--output", type=Path, default=default_output_dir())
    p_info = subs.add_parser("inspect", help="Consultar formatos sem baixar")
    p_info.add_argument("url", nargs="?", help="URL ou texto de compartilhamento")
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            data = inspect(_read_url(args.url))
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            result = download(
                _read_url(args.url), mode=args.mode, output_dir=args.output,
                progress_callback=_print_progress,
            )
            print(f"Arquivo: {result.path}")
            print(f"Tamanho: {result.size_bytes / (1024 * 1024):.2f} MiB")
            if result.height:
                print(f"Resolução reportada: {result.width or '?'}x{result.height}")
        return 0
    except (SocialVaultError, EOFError) as exc:
        print(f"\nErro: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelado pelo usuário.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
