"""Détecteurs (vision classique, sans entraînement) : acné, rides, taches, pores.

Principe commun : on compare chaque pixel à la peau VOISINE (flou gaussien
calculé uniquement sur la peau), ce qui rend la détection peu sensible à
l'éclairage global et à la carnation.
"""
import math

import cv2
import numpy as np
from skimage.filters import sato
from skimage.morphology import skeletonize

from . import config
from .face_regions import ZONES_ACNE, ZONES_PORES, ZONES_RIDES, ZONES_TACHES


def severity(value, scale):
    """Convertit une mesure brute en score 0-100 (saturation progressive)."""
    return round(100.0 * (1.0 - math.exp(-value / scale)), 1)


def level(score):
    if score < 25:
        return "faible"
    if score < 55:
        return "modéré"
    return "élevé"


def union(regions, names):
    m = np.zeros(regions.skin_mask.shape, np.uint8)
    for n in names:
        m |= regions.masks[n]
    return m


def masked_blur(channel, mask, sigma):
    """Moyenne locale de `channel` calculée uniquement sur les pixels de `mask`."""
    m = (mask > 0).astype(np.float32)
    num = cv2.GaussianBlur(channel * m, (0, 0), sigma)
    den = cv2.GaussianBlur(m, (0, 0), sigma)
    return num / np.maximum(den, 1e-3)


def zone_of(regions, x, y, names):
    for n in names:
        if regions.masks[n][int(y), int(x)]:
            return n
    return None


def area_cm2(mask, px_per_mm):
    return cv2.countNonZero(mask) / (px_per_mm * 10) ** 2


def lab_channels(bgr):
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    L = lab[..., 0] * (100.0 / 255.0)
    a = lab[..., 1] - 128.0
    return L, a


def _result(score_key, value, unit, elements, per_zone, extra=None):
    s = severity(value, config.SCORE_SCALE[score_key])
    out = {
        "score": s,
        "niveau": level(s),
        "mesure": round(value, 2),
        "unite": unit,
        "nombre": len(elements),
        "par_zone": per_zone,
        "elements": elements,
    }
    if extra:
        out.update(extra)
    return out


# ---------------------------------------------------------------------------
def detect_acne(regions, L, a):
    """Boutons : petites zones plus ROUGES que la peau autour, plutôt rondes."""
    ppm = regions.px_per_mm
    mask = union(regions, ZONES_ACNE)
    a_s = cv2.GaussianBlur(a, (0, 0), 1.5)
    bg = masked_blur(a, mask, 6 * ppm)
    delta = a_s - bg

    binary = ((delta > config.ACNE_RED_DELTA) & (mask > 0)).astype(np.uint8) * 255
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

    min_a = config.ACNE_MIN_AREA_MM2 * ppm ** 2
    max_a = config.ACNE_MAX_AREA_MM2 * ppm ** 2
    elements, per_zone = [], {z: 0 for z in ZONES_ACNE}
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        area = cv2.contourArea(c)
        if not (min_a <= area <= max_a):
            continue
        perim = cv2.arcLength(c, True)
        circ = 4 * math.pi * area / (perim ** 2 + 1e-6)
        if circ < config.ACNE_MIN_CIRCULARITY:
            continue
        (x, y), r = cv2.minEnclosingCircle(c)
        z = zone_of(regions, x, y, ZONES_ACNE)
        if z is None:
            continue
        per_zone[z] += 1
        m = np.zeros(mask.shape, np.uint8)
        cv2.drawContours(m, [c], -1, 255, -1)
        elements.append({
            "x": round(x), "y": round(y), "rayon": round(r, 1), "zone": z,
            "surface_mm2": round(area / ppm ** 2, 1),
            "rougeur": round(float(delta[m > 0].mean()), 1),
        })
    return _result("acne", len(elements), "lésions", elements, per_zone)


# ---------------------------------------------------------------------------
def detect_wrinkles(regions, L):
    """Rides : lignes fines plus SOMBRES, longues et étirées (filtre de crêtes)."""
    ppm = regions.px_per_mm
    full = np.zeros(L.shape, np.uint8)
    lengths, per_zone, elements = 0.0, {}, []

    for z in ZONES_RIDES:
        zmask = regions.masks[z]
        if cv2.countNonZero(zmask) == 0:
            per_zone[z] = 0.0
            continue
        x, y, w, h = cv2.boundingRect(zmask)
        pad = 10
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(L.shape[1], x + w + pad), min(L.shape[0], y + h + pad)
        sub_mask = zmask[y0:y1, x0:x1]
        sub = L[y0:y1, x0:x1]
        # Luminance relative à la peau voisine (=1 sur peau uniforme)
        rel = sub / np.maximum(masked_blur(sub, sub_mask, 5 * ppm), 1.0)
        rel = np.where(sub_mask > 0, rel, 1.0).astype(np.float32)
        ridge = sato(rel, sigmas=config.WRINKLE_SIGMAS, black_ridges=True)

        # On ignore une bande au bord de la zone (effet de bord du filtre, cheveux)
        b = int(2 * max(config.WRINKLE_SIGMAS)) * 2 + 1
        inner = cv2.erode(sub_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (b, b)))
        binary = ((ridge > config.WRINKLE_THRESHOLD) & (inner > 0)).astype(np.uint8)
        n, lab, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        keep = np.zeros_like(binary)
        zone_len = 0.0
        for i in range(1, n):
            comp = (lab == i)
            skel_len = skeletonize(comp).sum() / ppm   # mm
            pts = np.column_stack(np.nonzero(comp))[:, ::-1].astype(np.float32)
            (_, _), (rw, rh), _ = cv2.minAreaRect(pts)
            elong = max(rw, rh) / max(min(rw, rh), 1.0)
            if skel_len < config.WRINKLE_MIN_LENGTH_MM or elong < config.WRINKLE_MIN_ELONGATION:
                continue
            keep[comp] = 255
            zone_len += skel_len
            elements.append({"zone": z, "longueur_mm": round(float(skel_len), 1)})
        full[y0:y1, x0:x1] |= keep
        lengths += float(zone_len)
        per_zone[z] = round(float(zone_len), 1)

    zone_area = area_cm2(union(regions, ZONES_RIDES), ppm)
    density = lengths / zone_area if zone_area > 0 else 0.0
    return _result("rides", density, "mm/cm²", elements, per_zone,
                   {"longueur_totale_mm": round(lengths, 1), "masque": full})


# ---------------------------------------------------------------------------
def detect_spots(regions, L, a):
    """Taches : zones plus SOMBRES (pas rouges), plus grandes qu'un pore."""
    ppm = regions.px_per_mm
    mask = union(regions, ZONES_TACHES)
    L_s = cv2.GaussianBlur(L, (0, 0), 1.5)
    a_s = cv2.GaussianBlur(a, (0, 0), 1.5)
    dark = masked_blur(L, mask, 8 * ppm) - L_s
    red = a_s - masked_blur(a, mask, 8 * ppm)

    binary = ((dark > config.SPOT_DARK_DELTA) & (red < config.SPOT_MAX_RED_DELTA)
              & (mask > 0)).astype(np.uint8) * 255
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))

    min_a = config.SPOT_MIN_AREA_MM2 * ppm ** 2
    max_a = config.SPOT_MAX_AREA_MM2 * ppm ** 2
    elements, per_zone, covered = [], {z: 0 for z in ZONES_TACHES}, 0.0
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        area = cv2.contourArea(c)
        if not (min_a <= area <= max_a):
            continue
        (cx, cy), (rw, rh), _ = cv2.minAreaRect(c)
        if max(rw, rh) / max(min(rw, rh), 1.0) > 4:      # trop allongé => ride / ombre
            continue
        z = zone_of(regions, cx, cy, ZONES_TACHES)
        if z is None:
            continue
        per_zone[z] += 1
        covered += area
        x, y, w, h = cv2.boundingRect(c)
        elements.append({"x": x, "y": y, "w": w, "h": h, "zone": z,
                         "surface_mm2": round(area / ppm ** 2, 1)})
    coverage = 100.0 * covered / max(cv2.countNonZero(mask), 1)
    return _result("taches", coverage, "% surface", elements, per_zone)


# ---------------------------------------------------------------------------
def detect_pores(regions, L):
    """Pores / petits trous : minuscules points sombres (transformée black-hat)."""
    ppm = regions.px_per_mm
    mask = union(regions, ZONES_PORES)
    gray = cv2.GaussianBlur((L * 2.55).astype(np.uint8), (3, 3), 0)
    k = config.PORE_BLACKHAT_KSIZE
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT,
                                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    binary = ((blackhat > config.PORE_THRESHOLD) & (mask > 0)).astype(np.uint8)

    n, _, stats, cents = cv2.connectedComponentsWithStats(binary, connectivity=8)
    max_a = config.PORE_MAX_AREA_MM2 * ppm ** 2
    elements, per_zone = [], {z: 0 for z in ZONES_PORES}
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        w, h = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        if not (config.PORE_MIN_AREA_PX <= area <= max_a):
            continue
        if max(w, h) / max(min(w, h), 1) > 2.5:
            continue
        x, y = cents[i]
        z = zone_of(regions, x, y, ZONES_PORES)
        if z is None:
            continue
        per_zone[z] += 1
        elements.append({"x": round(x), "y": round(y), "zone": z})

    zone_area = area_cm2(mask, ppm)
    density = len(elements) / zone_area if zone_area > 0 else 0.0
    return _result("pores", density, "pores/cm²", elements, per_zone)
