#!/usr/bin/env bash
# Lance le miroir sur l'écran du Pi depuis SSH (une seule instance).
cd ~/skin_ai
if pgrep -x -f ".venv/bin/python -m mirror.app --backend opencv" >/dev/null; then
  echo "miroir deja lance"
else
  export DISPLAY=:0 XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 QT_QPA_PLATFORM=xcb
  setsid nohup .venv/bin/python -m mirror.app --backend opencv > ~/skin_history/miroir.log 2>&1 < /dev/null &
  echo "miroir lance"
fi
