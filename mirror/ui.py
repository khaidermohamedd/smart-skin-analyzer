"""Écrans du miroir. Fond NOIR = zone réfléchissante du miroir sans tain : seuls les textes
et les couleurs claires traversent le miroir. Le texte est dessiné avec Pillow (accents)."""
import math
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import config

W, H = config.SCREEN_W, config.SCREEN_H
WHITE = (255, 255, 255)
GREY = (150, 150, 150)
COLORS = {"acne": (255, 80, 80), "rides": (0, 200, 255), "taches": (255, 150, 0), "pores": (240, 230, 60)}
LABELS = {"acne": "Acné", "rides": "Rides", "taches": "Taches", "pores": "Pores"}

_FONT_CANDIDATES = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"]
_FONT_BOLD = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"]
_cache = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _cache:
        for path in (_FONT_BOLD if bold else _FONT_CANDIDATES):
            if Path(path).exists():
                _cache[key] = ImageFont.truetype(path, size)
                break
        else:
            _cache[key] = ImageFont.load_default()
    return _cache[key]


def _canvas():
    img = Image.new("RGB", (W, H), (0, 0, 0))
    return img, ImageDraw.Draw(img)


def _center(d, y, text, size, color=WHITE, bold=False):
    f = font(size, bold)
    w = d.textlength(text, font=f)
    d.text(((W - w) / 2, y), text, font=f, fill=color)


def _to_bgr(img):
    return np.array(img)[:, :, ::-1].copy()


def _sensor_line(s):
    parts = []
    if s.get("t_air") is not None:
        parts.append(f"{s['t_air']:.1f} °C")
    if s.get("humidite") is not None:
        parts.append(f"{s['humidite']:.0f} % d'humidité")
    return "   ·   ".join(parts)


# ---------------------------------------------------------------------------
def screen_idle(sensors, esp_ok):
    img, d = _canvas()
    now = datetime.now()
    _center(d, 120, now.strftime("%H:%M"), 96, WHITE, bold=True)
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
            "septembre", "octobre", "novembre", "décembre"]
    _center(d, 240, f"{jours[now.weekday()]} {now.day} {mois[now.month - 1]}", 26, GREY)
    _center(d, 290, _sensor_line(sensors), 22, GREY)
    alpha = int(140 + 115 * (0.5 + 0.5 * math.sin(time.time() * 2)))
    _center(d, 390, "Approchez-vous du miroir pour analyser votre peau", 22, (alpha, alpha, alpha))
    if not esp_ok:
        d.text((10, H - 24), "capteurs non connectés - ESPACE pour lancer une analyse", font=font(14), fill=(200, 80, 80))
    return _to_bgr(img)


def guide_message(dist):
    """(message, couleur) selon la distance du visage (None = inconnue)."""
    if dist is None:
        return "Placez votre visage face au miroir", WHITE
    if dist > config.DIST_MAX_MM:
        return "Rapprochez-vous un peu", (0, 200, 255)
    if dist < config.DIST_MIN_MM:
        return "Reculez un peu", (255, 150, 0)
    return "Parfait, ne bougez plus", (0, 230, 120)


def screen_guide(dist):
    img, d = _canvas()
    msg, col = guide_message(dist)
    _center(d, 150, msg, 40, col, bold=True)
    # Jauge de distance : zone idéale en vert
    x0, x1, y = 150, W - 150, 280
    lo, hi = 150, 900
    sx = lambda v: x0 + (min(max(v, lo), hi) - lo) / (hi - lo) * (x1 - x0)
    d.rectangle([x0, y, x1, y + 14], outline=GREY)
    d.rectangle([sx(config.DIST_MIN_MM), y, sx(config.DIST_MAX_MM), y + 14], fill=(0, 120, 60))
    if dist is not None:
        cx = sx(dist)
        d.polygon([(cx, y - 4), (cx - 10, y - 22), (cx + 10, y - 22)], fill=WHITE)
        _center(d, y + 30, f"{dist / 10:.0f} cm", 22, GREY)
    _center(d, 400, "Regardez droit devant vous, cheveux dégagés du front", 20, GREY)
    return _to_bgr(img)


def screen_countdown(n):
    img, d = _canvas()
    _center(d, 110, str(n), 200, WHITE, bold=True)
    _center(d, 380, "Ne bougez plus...", 28, GREY)
    return _to_bgr(img)


def screen_analysis(t0):
    img, d = _canvas()
    t = time.time() - t0
    cx, cy, r = W // 2, 190, 60
    for i in range(12):                       # roue de chargement
        a = 2 * math.pi * i / 12 + t * 4
        k = (i + 1) / 12
        d.ellipse([cx + r * math.cos(a) - 7, cy + r * math.sin(a) - 7,
                   cx + r * math.cos(a) + 7, cy + r * math.sin(a) + 7], fill=(int(160 * k), int(60 * k), int(255 * k)))
    _center(d, 300, "Analyse de la peau en cours", 32, WHITE, bold=True)
    _center(d, 350, f"{t:.0f} s  -  acné, rides, taches, pores", 22, GREY)
    return _to_bgr(img)


def screen_error(title, details=()):
    img, d = _canvas()
    _center(d, 150, title, 34, (255, 90, 90), bold=True)
    for i, line in enumerate(details[:3]):
        _center(d, 220 + 36 * i, line, 22, GREY)
    return _to_bgr(img)


def screen_results(report, sensors, tips, previous=None):
    img, d = _canvas()
    score = report["score_peau"]
    d.text((30, 18), "Score de peau", font=font(22), fill=GREY)
    d.text((30, 44), f"{score:.0f}", font=font(84, True), fill=WHITE)
    d.text((30 + d.textlength(f"{score:.0f}", font=font(84, True)) + 8, 92), "/100", font=font(26), fill=GREY)
    if previous is not None:
        delta = score - previous
        col = (0, 230, 120) if delta >= 0 else (255, 120, 80)
        d.text((30, 140), f"{'+' if delta >= 0 else ''}{delta:.0f} depuis la dernière analyse", font=font(18), fill=col)

    # Capteurs (colonne de droite)
    y = 26
    for label, key, fmt in (("Peau", "t_visage", "{:.1f} °C"), ("Air", "t_air", "{:.1f} °C"),
                            ("Humidité", "humidite", "{:.0f} %")):
        v = sensors.get(key)
        d.text((W - 230, y), label, font=font(18), fill=GREY)
        d.text((W - 120, y), fmt.format(v) if v is not None else "-", font=font(18, True), fill=WHITE)
        y += 30

    # 4 critères : barre de sévérité (plus la barre est longue, plus c'est marqué)
    y = 185
    for key in ("acne", "rides", "taches", "pores"):
        r = report["criteres"][key]
        d.text((30, y), LABELS[key], font=font(22, True), fill=COLORS[key])
        d.text((165, y + 2), r["niveau"], font=font(18), fill=GREY)
        bx0, bx1 = 290, W - 160
        d.rectangle([bx0, y + 6, bx1, y + 20], fill=(45, 45, 45))
        d.rectangle([bx0, y + 6, bx0 + (bx1 - bx0) * r["score"] / 100, y + 20], fill=COLORS[key])
        n = r['nombre']
        detail = f"{n} détecté{'s' if n > 1 else ''}" if key in ("acne", "taches") else f"{r['mesure']} {r['unite']}"
        d.text((W - 150, y + 2), detail, font=font(16), fill=GREY)
        y += 42

    # Conseils
    y += 6
    for tip in tips:
        d.text((30, y), "•  " + tip, font=font(18), fill=WHITE)
        y += 26
    d.text((30, H - 22), "Indication cosmétique, pas un diagnostic médical.", font=font(13), fill=(110, 110, 110))
    return _to_bgr(img)


# ---------------------------------------------------------------------------
def screen_live(frame, title, subtitle="", big=None, color=WHITE):
    """Caméra en temps réel, à SA résolution (pas réduite en 800x480 puis étirée) :
    l'image est nette sur un grand écran. Les textes sont dessinés sur de petits bandeaux."""
    img = frame.copy()
    h, w = img.shape[:2]
    k = h / H                                            # échelle par rapport à l'écran 800x480

    def band(y0, y1, text, size, col, bold=False):
        roi = img[y0:y1]
        roi[:] = (roi * 0.4).astype(np.uint8)            # bandeau assombri
        pil = Image.fromarray(roi[:, :, ::-1].copy())
        d = ImageDraw.Draw(pil)
        f = font(int(size * k), bold)
        tw = d.textlength(text, font=f)
        d.text(((w - tw) / 2, (y1 - y0 - size * k * 1.2) / 2), text, font=f, fill=col)
        img[y0:y1] = np.array(pil)[:, :, ::-1]

    band(0, int(64 * k), title, 28, color, bold=True)
    if subtitle:
        band(h - int(54 * k), h, subtitle, 20, GREY)
    # ovale de visée : où placer le visage
    cv2.ellipse(img, (w // 2, h // 2 + int(10 * k)), (int(120 * k), int(160 * k)), 0, 0, 360,
                (200, 200, 200), max(1, int(2 * k)), cv2.LINE_AA)
    if big is not None:                                  # chiffre à droite : le visage reste visible
        f = font(int(150 * k), True)
        x0, y0 = w - int(200 * k), int(110 * k)
        roi = img[y0:y0 + int(200 * k), x0:w]
        pil = Image.fromarray(roi[:, :, ::-1].copy())
        d = ImageDraw.Draw(pil)
        d.text((int(4 * k), int(4 * k)), big, font=f, fill=(0, 0, 0))
        d.text((0, 0), big, font=f, fill=WHITE)
        img[y0:y0 + roi.shape[0], x0:w] = np.array(pil)[:, :, ::-1]
    return img
