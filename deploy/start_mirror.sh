#!/usr/bin/env bash
# Lance le miroir en plein écran (appelé automatiquement à l'ouverture de session).
cd "$(dirname "$0")/.."
export QT_QPA_PLATFORM=xcb          # fenêtre OpenCV sous le bureau Wayland du Pi (via XWayland)
mkdir -p ~/skin_history
sleep 3                             # laisser le bureau et l'ESP32 démarrer
exec .venv/bin/python -m mirror.app "$@" >> ~/skin_history/miroir.log 2>&1
