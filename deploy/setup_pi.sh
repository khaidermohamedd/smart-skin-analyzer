#!/usr/bin/env bash
# Installation du miroir sur le Raspberry Pi 4 (Raspberry Pi OS 64 bits, avec bureau).
# À lancer UNE fois, depuis le dossier du projet copié sur le Pi :
#     cd ~/skin_ai && bash deploy/setup_pi.sh
set -e
cd "$(dirname "$0")/.."
PROJET="$(pwd)"
echo "=== Projet : $PROJET"

echo "=== 1/5 Paquets système (caméra, polices, port série)"
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip python3-picamera2 python3-serial python3-evdev fonts-dejavu-core

echo "=== 2/5 Environnement Python (garde accès à picamera2, installé par le système)"
python3 -m venv --system-site-packages .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install opencv-contrib-python scikit-image pillow onnxruntime
# MediaPipe n'est PAS installé : ses binaires ARM exigent des instructions (AES) absentes du
# processeur du Pi 4 -> plantage. Le moteur OpenCV 68 points est utilisé.

echo "=== 3/5 Accès au port série de l'ESP32"
sudo usermod -aG dialout "$USER"

echo "=== 4/5 Vérifications"
.venv/bin/python - <<'PY'
import cv2, skimage
print("OpenCV", cv2.__version__, "| contrib:", hasattr(cv2, "face"))
try:
    from picamera2 import Picamera2
    print("picamera2 OK, caméras détectées :", len(Picamera2.global_camera_info()))
except Exception as e:
    print("picamera2 : PROBLÈME ->", e)
from pathlib import Path
for m in ["acne_yolo.onnx", "wrinkle_unet.onnx", "face_detection_yunet.onnx", "lbfmodel.yaml"]:
    p = Path("skin_analyzer/models") / m
    print(f"modèle {m:28s}", "OK" if p.exists() else "MANQUANT")
PY

echo "=== 5/5 Démarrage automatique du miroir à l'ouverture de session"
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/skin-mirror.desktop <<EOF
[Desktop Entry]
Type=Application
Name=Skin Mirror
Exec=bash $PROJET/deploy/start_mirror.sh
X-GNOME-Autostart-enabled=true
EOF
chmod +x deploy/start_mirror.sh
echo
echo "Installation terminée. Redémarrez le Pi (sudo reboot) : le miroir se lancera tout seul."
echo "Test manuel :  bash deploy/start_mirror.sh"
