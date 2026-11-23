#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$(dirname "$0")"
echo "[SocialVault] Instalando motor no Termux..."
pkg update
pkg install -y python ffmpeg
python -m pip install -e .
echo "Pronto. Opcional: execute termux-setup-storage para salvar nos Downloads do Android."
echo "Uso: python -m socialvault download 'LINK' --mode mp4"
