"""Test par injection : on dessine de faux défauts sur un visage réel et on
vérifie que chaque détecteur les retrouve (et ne s'emballe pas sans défaut).

    python -m tests.test_synthetic
"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from skin_analyzer.analyzer import SkinAnalyzer               # noqa: E402
from skin_analyzer.detectors import (detect_acne, detect_pores,  # noqa: E402
                                     detect_spots, detect_wrinkles, lab_channels)

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "astronaut.png"


def inner_points(mask, n, rng, margin=25, spacing=None):
    """n points au hasard bien à l'intérieur d'un masque, espacés d'au moins `spacing` px."""
    spacing = spacing or 2 * margin
    core = cv2.erode(mask, np.ones((2 * margin + 1,) * 2, np.uint8))
    ys, xs = np.nonzero(core)
    pts = []
    for i in rng.permutation(len(xs)):
        p = (int(xs[i]), int(ys[i]))
        if all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 >= spacing ** 2 for q in pts):
            pts.append(p)
            if len(pts) == n:
                break
    assert len(pts) == n, "zone trop petite pour placer les défauts"
    return pts


def blend_disk(img, center, radius, color, alpha):
    overlay = img.copy()
    cv2.circle(overlay, center, radius, color, -1, cv2.LINE_AA)
    blurred = cv2.GaussianBlur(overlay, (0, 0), radius * 0.3 + 0.5)
    m = np.zeros(img.shape[:2], np.float32)
    cv2.circle(m, center, radius + 2, 1.0, -1)
    m = cv2.GaussianBlur(m, (0, 0), 1.5)[..., None] * alpha
    img[:] = (img * (1 - m) + blurred * m).astype(np.uint8)


def run_detectors(regions):
    L, a = lab_channels(regions.image)
    return {
        "acne": detect_acne(regions, L, a),
        "rides": detect_wrinkles(regions, L),
        "taches": detect_spots(regions, L, a),
        "pores": detect_pores(regions, L),
    }


def main():
    rng = np.random.default_rng(0)
    analyzer = SkinAnalyzer()
    regions = analyzer.extractor.extract(cv2.imread(str(SAMPLE)))
    assert regions is not None, "visage non détecté"
    base = run_detectors(regions)

    img = regions.image
    ppm = regions.px_per_mm
    cheeks = regions.masks["joue_g"] | regions.masks["joue_d"]

    # 1) Acné : 6 disques rouges de ~3 mm sur les joues
    acne_pts = inner_points(cheeks, 6, rng, margin=15, spacing=35)
    for x, y in acne_pts:
        blend_disk(img, (int(x), int(y)), int(1.5 * ppm), (60, 60, 200), 0.55)

    # 2) Taches : 3 disques brun foncé de ~5 mm sur les joues
    spot_mask = cheeks.copy()
    for x, y in acne_pts:
        cv2.circle(spot_mask, (int(x), int(y)), 40, 0, -1)
    spot_pts = inner_points(spot_mask, 3, rng, margin=20, spacing=45)
    for x, y in spot_pts:
        blend_disk(img, (int(x), int(y)), int(2.5 * ppm), (60, 90, 120), 0.45)

    # 3) Rides : 3 lignes sombres sur la partie visible du front et des pattes d'oie
    lines = np.zeros(img.shape[:2], np.uint8)
    fx, fy, fw, fh = cv2.boundingRect(regions.masks["front"])
    for k in range(3):
        y = fy + int(fh * (0.3 + 0.2 * k))
        cv2.line(lines, (fx, y), (fx + fw, y), 255, 3, cv2.LINE_AA)
    for z in ("patte_oie_g", "patte_oie_d"):
        zx, zy, zw, zh = cv2.boundingRect(regions.masks[z])
        cv2.line(lines, (zx, zy + zh // 2), (zx + zw, zy + zh // 3), 255, 3, cv2.LINE_AA)
    core = np.zeros_like(lines)
    for z in ("front", "patte_oie_g", "patte_oie_d"):
        core |= cv2.erode(regions.masks[z], np.ones((17, 17), np.uint8))
    lines &= core
    alpha = cv2.GaussianBlur(lines.astype(np.float32) / 255, (0, 0), 1.0)[..., None] * 0.5
    img[:] = (img * (1 - alpha) + np.array([90, 110, 140]) * alpha).astype(np.uint8)

    # 4) Pores : 25 petits points sombres sur le nez
    pore_pts = inner_points(regions.masks["nez"], 25, rng, margin=6, spacing=8)
    for x, y in pore_pts:
        cv2.circle(img, (int(x), int(y)), 1, (70, 85, 110), -1, cv2.LINE_AA)

    after = run_detectors(regions)

    def recall(points, found, key_xy, tol):
        hits = sum(any((px - fx) ** 2 + (py - fy) ** 2 <= tol ** 2 for fx, fy in map(key_xy, found))
                   for px, py in points)
        return hits / len(points)

    spot_center = lambda t: (t["x"] + t["w"] / 2, t["y"] + t["h"] / 2)
    rides_found = (after["rides"]["masque"] > 0) & (lines > 127)
    scores = {
        "acne":   recall(acne_pts, after["acne"]["elements"], lambda a: (a["x"], a["y"]), 2 * ppm),
        "taches": recall(spot_pts, after["taches"]["elements"], spot_center, 3 * ppm),
        "pores":  recall(pore_pts, after["pores"]["elements"], lambda p: (p["x"], p["y"]), 3),
        "rides":  rides_found.sum() / max((lines > 127).sum(), 1),
    }
    print(f"{'critère':8s} {'détecté':>8s}  résultat   (fausses détections avant injection)")
    ok_all = True
    for k, r in scores.items():
        ok = r >= 0.6
        ok_all &= ok
        print(f"{k:8s} {r:8.0%}  {'OK' if ok else 'ÉCHEC':8s}   {base[k]['nombre']}")

    out = Path(__file__).resolve().parent.parent / "results" / "test_injection.jpg"
    out.parent.mkdir(exist_ok=True)
    from skin_analyzer.visualize import annotate
    report = {"score_peau": 0, "criteres": after,
              "qualite": {"avertissements": []}}
    cv2.imwrite(str(out), annotate(report, regions))
    print(f"Image : {out}")
    analyzer.close()
    return ok_all


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(0 if main() else 1)
