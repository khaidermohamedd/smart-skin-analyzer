#!/usr/bin/env bash
# Lance un entraînement dans Ubuntu (WSL2), avec la carte graphique.
# Depuis Windows (PowerShell ou cmd) :
#   wsl -d skinai -u root -- bash /mnt/d/skin_ai/code/training/wsl_train.sh acne
#   wsl -d skinai -u root -- bash /mnt/d/skin_ai/code/training/wsl_train.sh wrinkles
#   wsl -d skinai -u root -- bash /mnt/d/skin_ai/code/training/wsl_train.sh acne --epochs 3
set -e
export SKIN_AI_DIR=/mnt/d/skin_ai
export SKIN_AI_DATA=/data/skin_ai/datasets     # copie locale (lecture rapide)
export SKIN_AI_RUNS=/mnt/d/skin_ai/runs        # résultats visibles depuis Windows
export HF_HOME=/data/skin_ai/hf_cache TORCH_HOME=/data/skin_ai/torch_cache
export YOLO_CONFIG_DIR=/data/skin_ai/yolo_cfg PYTHONUNBUFFERED=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True   # limite la fragmentation de la memoire GPU
cd /mnt/d/skin_ai/code
what="$1"; shift || true
case "$what" in
  acne)     module=training.train_acne ;;
  wrinkles) module=training.train_wrinkles ;;
  *) echo "usage: wsl_train.sh acne|wrinkles [options]"; exit 1 ;;
esac
# Journal lisible depuis Windows : D:\skin_aiuns\<acne|wrinkles>_train.log
mkdir -p "$SKIN_AI_RUNS"
log="$SKIN_AI_RUNS/${what}_train.log"
echo "=== Début : $(date '+%Y-%m-%d %H:%M:%S')  ($what $*) ===" >> "$log"
set +e
/opt/skinai/venv/bin/python -m "$module" "$@" 2>&1 | tee -a "$log"
code=${PIPESTATUS[0]}
echo "=== Fin : $(date '+%Y-%m-%d %H:%M:%S')  code=$code ===" >> "$log"
exit $code
