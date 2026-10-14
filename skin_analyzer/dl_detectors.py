"""Détecteurs d'acné et de rides basés sur les modèles d'apprentissage profond.

Ils renvoient exactement le même format que les détecteurs classiques (detectors.py),
pour que les scores, le rapport et l'affichage fonctionnent sans changement.
"""
import math

import cv2
import numpy as np
from skimage.morphology import skeletonize

from . import config
from .detectors import _result, area_cm2, union, zone_of
from .dl_models import AcneDetector, WrinkleSegmenter, ffhq_quad
from .face_regions import ZONES_ACNE

ZONES_RIDES_DL = ["front", "patte_oie_g", "patte_oie_d", "joue_g", "joue_d", "nez", "menton"]


class DLAcne:
    """YOLO11 (ACNE04). Le visage est remis à l'échelle des photos d'entraînement."""

    def __init__(self):
        self.det = AcneDetector()

    def __call__(self, regions):
        ppm = regions.px_per_mm
        k = config.ACNE_REF_EYE_DIST / regions.raw_eye_dist      # échelle ACNE04 / échelle de la photo
        img = cv2.resize(regions.crop, None, fx=k, fy=k,
                         interpolation=cv2.INTER_CUBIC if k > 1 else cv2.INTER_AREA)
        boxes = self.det.detect(img)
        to_norm = regions.scale / k                              # repère ACNE04 -> image normalisée
        # Tout le visage (hors yeux/lèvres) : les zones seules peuvent manquer des bords de joue
        mask = regions.face_mask | cv2.dilate(union(regions, ZONES_ACNE), np.ones((9, 9), np.uint8))
        H, W = mask.shape
        elements, per_zone = [], {z: 0 for z in ZONES_ACNE}
        for b in boxes:
            x0, y0, x1, y1 = (v * to_norm for v in (b["x0"], b["y0"], b["x1"], b["y1"]))
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            if not (0 <= cx < W and 0 <= cy < H) or not mask[int(cy), int(cx)]:
                continue
            z = zone_of(regions, cx, cy, ZONES_ACNE) or _nearest_zone(regions, cx, cy, ZONES_ACNE)
            per_zone[z] += 1
            r = max(x1 - x0, y1 - y0) / 2
            elements.append({"x": round(cx), "y": round(cy), "rayon": round(r, 1), "zone": z,
                             "surface_mm2": round(math.pi * r * r / ppm ** 2, 1),
                             "confiance": round(b["score"], 2)})
        return _result("acne_dl", len(elements), "lésions", elements, per_zone,
                       {"methode": "YOLO11 (ACNE04)"})


class DLWrinkles:
    """U-Net (FFHQ-Wrinkle). Visage aligné comme FFHQ, masque ramené dans l'image."""

    def __init__(self):
        self.seg = WrinkleSegmenter()

    def __call__(self, regions):
        ppm = regions.px_per_mm
        quad = ffhq_quad(*[np.asarray(p, np.float64) for p in regions.ffhq_points])
        mask, _ = self.seg.predict(regions.image, quad, tta=config.WRINKLE_TTA)
        mask &= regions.face_mask
        skel = skeletonize(mask > 0)
        total_mm = skel.sum() / ppm
        per_zone = {}
        for z in ZONES_RIDES_DL:
            per_zone[z] = round(float((skel & (regions.masks[z] > 0)).sum() / ppm), 1)
        n, lab = cv2.connectedComponents(mask, connectivity=8)
        elements = [{"longueur_mm": round(float((skel & (lab == i)).sum() / ppm), 1)} for i in range(1, n)]
        elements = [e for e in elements if e["longueur_mm"] >= 2]
        face_cm2 = area_cm2(regions.face_mask, ppm)
        density = total_mm / face_cm2 if face_cm2 > 0 else 0.0
        return _result("rides_dl", density, "mm/cm²", elements, per_zone,
                       {"longueur_totale_mm": round(float(total_mm), 1), "masque": mask,
                        "methode": "U-Net (FFHQ-Wrinkle)"})


def _nearest_zone(regions, x, y, names):
    best, dmin = names[0], 1e9
    for n in names:
        ys, xs = np.nonzero(regions.masks[n])
        if len(xs):
            d = np.min((xs - x) ** 2 + (ys - y) ** 2)
            if d < dmin:
                best, dmin = n, d
    return best
