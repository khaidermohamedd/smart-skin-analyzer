"""Dessin des résultats sur l'image + panneau de scores."""
import unicodedata

import cv2
import numpy as np

COLORS = {                       # BGR
    "acne": (40, 40, 230),
    "rides": (255, 200, 0),
    "taches": (0, 140, 255),
    "pores": (0, 230, 230),
    "zone": (200, 200, 200),
}
LABELS = {"acne": "Acne", "rides": "Rides", "taches": "Taches", "pores": "Pores"}


def _ascii(text):
    """OpenCV ne sait pas dessiner les accents."""
    text = text.replace("²", "2")
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def draw_landmarks(bgr, pts, step=3):
    out = bgr.copy()
    for x, y in pts[::step]:
        cv2.circle(out, (int(x), int(y)), 1, (0, 255, 0), -1)
    return out


def annotate(report, regions, show_zones=True):
    img = regions.image.copy()
    crit = report["criteres"]

    if show_zones:
        for m in regions.masks.values():
            cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(img, cnts, -1, COLORS["zone"], 1)

    wr = crit["rides"].get("masque")
    if wr is not None:
        img[wr > 0] = (0.4 * img[wr > 0] + 0.6 * np.array(COLORS["rides"])).astype(np.uint8)
    for p in crit["pores"]["elements"]:
        cv2.circle(img, (p["x"], p["y"]), 2, COLORS["pores"], -1)
    for s in crit["taches"]["elements"]:
        cv2.rectangle(img, (s["x"], s["y"]), (s["x"] + s["w"], s["y"] + s["h"]), COLORS["taches"], 2)
    for a in crit["acne"]["elements"]:
        cv2.circle(img, (a["x"], a["y"]), int(a["rayon"]) + 4, COLORS["acne"], 2)

    return np.hstack([img, _panel(report, img.shape[0])])


def _panel(report, height, width=360):
    panel = np.full((height, width, 3), 30, np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    y = 40
    cv2.putText(panel, "Score peau: %.0f/100" % report["score_peau"], (15, y), font, 0.75, (255, 255, 255), 2)
    y += 45
    for key, label in LABELS.items():
        r = report["criteres"][key]
        cv2.putText(panel, "%s (%s)" % (label, _ascii(r["niveau"])),
                    (15, y), font, 0.6, COLORS[key], 2)
        y += 22
        bar_w = int((width - 30) * r["score"] / 100)
        cv2.rectangle(panel, (15, y), (width - 15, y + 12), (80, 80, 80), -1)
        cv2.rectangle(panel, (15, y), (15 + bar_w, y + 12), COLORS[key], -1)
        y += 30
        cv2.putText(panel, "%s %s  (n=%d)" % (r["mesure"], _ascii(r["unite"]), r["nombre"]),
                    (15, y), font, 0.5, (220, 220, 220), 1)
        y += 40
    for w in report["qualite"]["avertissements"]:
        txt = _ascii(w)
        cv2.putText(panel, "! " + txt[:40], (15, y), font, 0.42, (80, 80, 255), 1)
        y += 20
    return panel
