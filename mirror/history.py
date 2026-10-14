"""Historique des analyses (une ligne JSON par analyse) pour suivre l'évolution de la peau."""
import json
from datetime import datetime

import cv2

from . import config


def save(payload, photo=None, annotated=None):
    config.HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    payload = dict(payload, id=stamp)
    with open(config.HISTORY_DIR / "historique.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    if config.SAVE_PHOTOS:
        if photo is not None:
            cv2.imwrite(str(config.HISTORY_DIR / f"{stamp}_photo.jpg"), photo)
        if annotated is not None:
            cv2.imwrite(str(config.HISTORY_DIR / f"{stamp}_analyse.jpg"), annotated)
    return stamp


def previous_score():
    """Score de la dernière analyse enregistrée (pour afficher l'évolution), ou None."""
    f = config.HISTORY_DIR / "historique.jsonl"
    if not f.exists():
        return None
    lines = f.read_text(encoding="utf-8").strip().splitlines()
    try:
        return json.loads(lines[-1])["score_peau"] if lines else None
    except (ValueError, KeyError):
        return None
