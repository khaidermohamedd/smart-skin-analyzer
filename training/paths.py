"""Emplacements communs.

Windows : tout est sous D:/skin_ai.
WSL2 (entraînement GPU) : données copiées dans le disque Linux (/data/skin_ai/datasets,
lecture beaucoup plus rapide), résultats écrits sur D: (/mnt/d/skin_ai/runs) pour être
visibles depuis Windows. Voir training/wsl_train.sh.
"""
import os
from pathlib import Path

SKIN_AI_DIR = Path(os.environ.get("SKIN_AI_DIR", "D:/skin_ai"))
DATA = Path(os.environ.get("SKIN_AI_DATA", SKIN_AI_DIR / "datasets"))
RUNS = Path(os.environ.get("SKIN_AI_RUNS", SKIN_AI_DIR / "runs"))
MODELS_OUT = Path(__file__).resolve().parent.parent / "skin_analyzer" / "models"
