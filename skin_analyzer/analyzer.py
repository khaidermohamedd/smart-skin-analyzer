"""Point d'entrée du module : image BGR -> rapport (dict JSON-sérialisable)."""
import time
from datetime import datetime

import cv2
import numpy as np

from . import config
from .detectors import (detect_acne, detect_pores, detect_spots, detect_wrinkles,
                        lab_channels, level, severity)
from .face_regions import FaceRegionExtractor


def _load_dl():
    """Charge les modèles profonds présents ; sinon les détecteurs classiques sont utilisés."""
    models = {}
    if not config.USE_DL:
        return models
    if config.ACNE_MODEL.exists():
        from .dl_detectors import DLAcne
        models["acne"] = DLAcne()
    if config.WRINKLE_MODEL.exists():
        from .dl_detectors import DLWrinkles
        models["rides"] = DLWrinkles()
    return models

# Poids des critères dans le score global de peau
WEIGHTS = {"acne": 0.35, "rides": 0.25, "taches": 0.2, "pores": 0.2}


class SkinAnalyzer:
    def __init__(self, backend="auto"):
        self.extractor = FaceRegionExtractor(backend)
        self.dl = _load_dl()

    def close(self):
        self.extractor.close()

    def check_quality(self, regions, L):
        """Avertissements sur la qualité de la capture (distance, lumière, netteté)."""
        warnings = []
        if regions.raw_eye_dist < config.MIN_EYE_DIST_RAW:
            warnings.append("Visage trop loin ou caméra trop peu résolue : rapprochez-vous.")
        skin = regions.skin_mask > 0
        brightness = float(L[skin].mean() * 2.55)
        if brightness < config.MIN_BRIGHTNESS:
            warnings.append("Éclairage insuffisant.")
        elif brightness > config.MAX_BRIGHTNESS:
            warnings.append("Image surexposée.")
        gray = cv2.cvtColor(regions.image, cv2.COLOR_BGR2GRAY)
        sharp = float(cv2.Laplacian(gray, cv2.CV_64F)[skin].var())
        if sharp < config.MIN_SHARPNESS:
            warnings.append("Image floue : restez immobile.")
        return {
            "distance_yeux_px": round(regions.raw_eye_dist, 1),
            "luminosite": round(brightness, 1),
            "nettete": round(sharp, 1),
            "valide": not warnings,
            "avertissements": warnings,
        }

    def analyze(self, bgr):
        """Retourne (rapport, regions) ou (None, None) si aucun visage détecté."""
        t0 = time.perf_counter()
        regions = self.extractor.extract(bgr)
        if regions is None:
            return None, None

        L, a = lab_channels(regions.image)
        results = {
            "acne": self.dl["acne"](regions) if "acne" in self.dl else detect_acne(regions, L, a),
            "rides": self.dl["rides"](regions) if "rides" in self.dl else detect_wrinkles(regions, L),
            "taches": detect_spots(regions, L, a),
            "pores": detect_pores(regions, L),
        }
        _drop_pores_inside_lesions(results)
        global_sev = sum(WEIGHTS[k] * results[k]["score"] for k in WEIGHTS)
        report = {
            "date": datetime.now().isoformat(timespec="seconds"),
            "moteur_points": regions.backend,
            "qualite": self.check_quality(regions, L),
            "score_peau": round(100 - global_sev, 1),   # 100 = peau sans défaut visible
            "severite_globale": level(global_sev),
            "criteres": results,
            "duree_ms": round((time.perf_counter() - t0) * 1000),
        }
        return report, regions


def _drop_pores_inside_lesions(results):
    """Un bouton ou une tache ne doit pas être compté aussi comme pore."""
    pores = results["pores"]
    zones = [(a["x"], a["y"], a["rayon"] + 3) for a in results["acne"]["elements"]]
    zones += [(t["x"] + t["w"] / 2, t["y"] + t["h"] / 2, max(t["w"], t["h"]) / 2 + 3)
              for t in results["taches"]["elements"]]
    kept = [p for p in pores["elements"]
            if all((p["x"] - x) ** 2 + (p["y"] - y) ** 2 > r ** 2 for x, y, r in zones)]
    if len(kept) == len(pores["elements"]):
        return
    removed = len(pores["elements"]) - len(kept)
    for z in pores["par_zone"]:
        pores["par_zone"][z] = sum(p["zone"] == z for p in kept)
    pores["mesure"] = round(pores["mesure"] * len(kept) / len(pores["elements"]), 2)
    pores["score"] = severity(pores["mesure"], config.SCORE_SCALE["pores"])
    pores["niveau"] = level(pores["score"])
    pores["elements"], pores["nombre"] = kept, len(kept)
    pores["exclus_lesions"] = removed


def report_to_json(report):
    """Copie du rapport sans les données lourdes (masques, listes de points)."""
    out = {k: v for k, v in report.items() if k != "criteres"}
    out["criteres"] = {}
    for name, r in report["criteres"].items():
        out["criteres"][name] = {k: v for k, v in r.items()
                                 if not isinstance(v, np.ndarray) and k != "elements"}
    return out
