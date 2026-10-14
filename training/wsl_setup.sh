#!/usr/bin/env bash
# Installe l'environnement d'entraînement dans Ubuntu (WSL2). À lancer une seule fois :
#   wsl -d skinai -u root -- bash /mnt/d/skin_ai/code/training/wsl_setup.sh
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip libgl1 libglib2.0-0 rsync > /dev/null
python3 -m venv /opt/skinai/venv
PIP=/opt/skinai/venv/bin/pip
$PIP install -q --upgrade pip
$PIP install -q torch torchvision --index-url https://download.pytorch.org/whl/cu126
$PIP install -q ultralytics segmentation-models-pytorch albumentations scikit-image onnx onnxslim
# Version d'OpenCV sans interface graphique (serveur), au cas où ultralytics a installé l'autre
$PIP uninstall -y -q opencv-python || true
$PIP install -q --force-reinstall --no-deps opencv-python-headless
/opt/skinai/venv/bin/python - <<'PY'
import torch, cv2, ultralytics, segmentation_models_pytorch as smp
print("torch", torch.__version__, "| CUDA :", torch.cuda.is_available(), "|", torch.cuda.get_device_name(0))
print("opencv", cv2.__version__, "| ultralytics", ultralytics.__version__, "| smp", smp.__version__)
PY
