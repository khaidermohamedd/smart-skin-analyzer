#!/usr/bin/env bash
# Attend la fin de l'entraînement de l'acné, puis lance celui des rides.
#   wsl -d skinai -u root -- bash /mnt/d/skin_ai/code/training/wsl_queue.sh
echo "En attente de la fin de l'entrainement ACNE (verification chaque minute)..."
while pgrep -f "training.train_acne" > /dev/null; do sleep 60; done
echo "ACNE termine : $(date '+%Y-%m-%d %H:%M:%S'). Demarrage des RIDES dans 30 s..."
sleep 30
exec bash /mnt/d/skin_ai/code/training/wsl_train.sh wrinkles
