"""Génère docs/Guide_Realisation_Skin_Analyzer.pdf

    python docs/build_guide.py

Les scores des modèles sont lus automatiquement dans D:/skin_ai/runs/*/test_metrics.json
s'ils existent : relancer ce script après l'entraînement met le guide à jour.
"""
import json
from datetime import date
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (CondPageBreak, Image, KeepTogether, PageBreak, Paragraph, Preformatted,
                                SimpleDocTemplate, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"
OUT = HERE / "Guide_Realisation_Skin_Analyzer.pdf"
RUNS = Path("D:/skin_ai/runs")

# --- Polices (Arial / Consolas de Windows : accents et flèches) -------------
F = "C:/Windows/Fonts/"
pdfmetrics.registerFont(TTFont("Body", F + "arial.ttf"))
pdfmetrics.registerFont(TTFont("Body-Bold", F + "arialbd.ttf"))
pdfmetrics.registerFont(TTFont("Body-Italic", F + "ariali.ttf"))
pdfmetrics.registerFont(TTFont("Mono", F + "consola.ttf"))
pdfmetrics.registerFont(TTFont("Mono-Bold", F + "consolab.ttf"))
from reportlab.pdfbase.pdfmetrics import registerFontFamily  # noqa: E402
registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body-Italic", boldItalic="Body-Bold")
registerFontFamily("Mono", normal="Mono", bold="Mono-Bold", italic="Mono", boldItalic="Mono-Bold")

INK = colors.HexColor("#1d2433")
ACCENT = colors.HexColor("#2f5d8a")
MUTED = colors.HexColor("#5b6472")
CODE_BG = colors.HexColor("#f3f5f8")
RULE = colors.HexColor("#d5dae2")
OK = colors.HexColor("#2e7d4f")
WARN = colors.HexColor("#a8641b")

S = {
    "title": ParagraphStyle("title", fontName="Body-Bold", fontSize=26, leading=32, textColor=INK, alignment=TA_CENTER),
    "subtitle": ParagraphStyle("subtitle", fontName="Body", fontSize=14, leading=20, textColor=ACCENT, alignment=TA_CENTER),
    "meta": ParagraphStyle("meta", fontName="Body", fontSize=10.5, leading=15, textColor=MUTED, alignment=TA_CENTER),
    "h1": ParagraphStyle("h1", fontName="Body-Bold", fontSize=17, leading=22, textColor=ACCENT, spaceBefore=6, spaceAfter=10),
    "h2": ParagraphStyle("h2", fontName="Body-Bold", fontSize=13, leading=17, textColor=INK, spaceBefore=12, spaceAfter=6,
                         keepWithNext=1),
    "h3": ParagraphStyle("h3", fontName="Body-Bold", fontSize=11, leading=15, textColor=ACCENT, spaceBefore=8, spaceAfter=4,
                         keepWithNext=1),
    "toctitle": ParagraphStyle("toctitle", fontName="Body-Bold", fontSize=17, leading=22, textColor=ACCENT, spaceAfter=12),
    "body": ParagraphStyle("body", fontName="Body", fontSize=10, leading=14.5, textColor=INK, spaceAfter=6),
    "bullet": ParagraphStyle("bullet", fontName="Body", fontSize=10, leading=14, textColor=INK,
                             leftIndent=14, bulletIndent=4, spaceAfter=2),
    "cell": ParagraphStyle("cell", fontName="Body", fontSize=8.8, leading=11.5, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName="Body-Bold", fontSize=8.8, leading=11.5, textColor=colors.white),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=8.3, leading=10.8, textColor=INK),
    "caption": ParagraphStyle("caption", fontName="Body-Italic", fontSize=8.8, leading=12, textColor=MUTED,
                              alignment=TA_CENTER, spaceAfter=10),
    "note": ParagraphStyle("note", fontName="Body", fontSize=9.5, leading=13.5, textColor=INK),
    "toc1": ParagraphStyle("toc1", fontName="Body-Bold", fontSize=10, leading=12.5, leftIndent=0, spaceBefore=2),
    "toc2": ParagraphStyle("toc2", fontName="Body", fontSize=8.8, leading=10.5, leftIndent=16, textColor=MUTED),
    "ref": ParagraphStyle("ref", fontName="Body", fontSize=8.6, leading=11, textColor=INK, leftIndent=14, bulletIndent=4, spaceAfter=1),
}


# --- Helpers -----------------------------------------------------------------
class Doc(SimpleDocTemplate):
    def afterFlowable(self, f):
        if isinstance(f, Paragraph) and f.style.name in ("h1", "h2"):
            level = 0 if f.style.name == "h1" else 1
            key = f"h{id(f)}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(f.getPlainText(), key, level=level)
            self.notify("TOCEntry", (level, f.getPlainText(), self.page, key))


story = []


def h1(t):
    story.append(CondPageBreak(9 * cm))      # nouvelle page seulement s'il reste peu de place
    story.append(Paragraph(t, S["h1"]))
    story.append(Rule())


def h2(t):
    story.append(Paragraph(t, S["h2"]))


def h3(t):
    story.append(Paragraph(t, S["h3"]))


def p(t):
    story.append(Paragraph(t, S["body"]))


def bullets(items):
    for it in items:
        story.append(Paragraph(it, S["bullet"], bulletText="•"))
    story.append(Spacer(1, 4))


def code(txt):
    pre = Preformatted(txt.strip("\n"), S["code"])
    t = Table([[pre]], colWidths=[16.4 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 8))


def table(rows, widths, header=True):
    data = []
    for i, r in enumerate(rows):
        st = S["cellb"] if header and i == 0 else S["cell"]
        data.append([Paragraph(str(c), st) for c in r])
    t = Table(data, colWidths=[w * cm for w in widths], repeatRows=1 if header else 0)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), ACCENT))
    for i in range(1 if header else 0, len(rows)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f7f9fb")))
    t.setStyle(TableStyle(style))
    story.append(t)
    story.append(Spacer(1, 8))


def callout(t, color=ACCENT, title=None):
    content = [Paragraph(f"<b>{title}</b>", S["note"])] if title else []
    content.append(Paragraph(t, S["note"]))
    tb = Table([[content]], colWidths=[16.4 * cm])
    tb.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f5f8fc")),
        ("LINEBEFORE", (0, 0), (0, -1), 3, color),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(tb)
    story.append(Spacer(1, 10))


def figure(name, caption, width_cm=15):
    path = FIG / name
    if not path.exists():
        return
    img = Image(str(path))
    ratio = img.imageHeight / img.imageWidth
    img.drawWidth = width_cm * cm
    img.drawHeight = width_cm * cm * ratio
    story.append(KeepTogether([img, Spacer(1, 4), Paragraph(caption, S["caption"])]))


class Rule(Table):
    def __init__(self):
        super().__init__([[""]], colWidths=[16.4 * cm], rowHeights=[2])
        self.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 1.2, ACCENT)]))


def pipeline_diagram():
    """Schéma du pipeline : boîtes reliées par des flèches."""
    W, H = 16.4 * cm, 7.2 * cm
    d = Drawing(W, H)

    def box(x, y, w, h, title, sub, fill):
        d.add(Rect(x, y, w, h, rx=5, ry=5, fillColor=fill, strokeColor=ACCENT, strokeWidth=0.8))
        d.add(String(x + w / 2, y + h - 14, title, fontName="Body-Bold", fontSize=8.5,
                     fillColor=INK, textAnchor="middle"))
        for i, line in enumerate(sub):
            d.add(String(x + w / 2, y + h - 27 - i * 10, line, fontName="Body", fontSize=7,
                         fillColor=MUTED, textAnchor="middle"))

    def arrow(x0, y0, x1, y1):
        d.add(Line(x0, y0, x1, y1, strokeColor=ACCENT, strokeWidth=1))
        import math
        a = math.atan2(y1 - y0, x1 - x0)
        s = 5
        d.add(Polygon([x1, y1, x1 - s * math.cos(a - 0.4), y1 - s * math.sin(a - 0.4),
                       x1 - s * math.cos(a + 0.4), y1 - s * math.sin(a + 0.4)],
                      fillColor=ACCENT, strokeColor=ACCENT))

    light = colors.HexColor("#eef3f9")
    dl = colors.HexColor("#e8f3ec")
    cv = colors.HexColor("#fbf3e6")
    bw, bh = 3.5 * cm, 1.75 * cm
    y_top = H - bh - 4
    box(0, y_top, bw, bh, "1. Capture", ["caméra du miroir", "photo / flux vidéo"], light)
    box(4.2 * cm, y_top, bw, bh, "2. Points du visage", ["MediaPipe 478 pts", "ou OpenCV 68 pts"], light)
    box(8.4 * cm, y_top, bw, bh, "3. Normalisation", ["recadrage + échelle", "zones de peau"], light)
    box(12.6 * cm, y_top, bw + 0.3 * cm, bh, "4. Contrôle qualité", ["distance, lumière,", "netteté"], light)
    for x in (bw, 4.2 * cm + bw, 8.4 * cm + bw):
        arrow(x + 2, y_top + bh / 2, x + 0.7 * cm - 2, y_top + bh / 2)

    y_mid = y_top - bh - 0.9 * cm
    box(0, y_mid, 3.9 * cm, bh, "Acné : YOLO11", ["entraîné sur ACNE04", "(apprentissage profond)"], dl)
    box(4.15 * cm, y_mid, 3.9 * cm, bh, "Rides : U-Net", ["entraîné sur FFHQ-Wrinkle", "(apprentissage profond)"], dl)
    box(8.3 * cm, y_mid, 3.9 * cm, bh, "Taches", ["vision classique", "(contraste L*a*b*)"], cv)
    box(12.45 * cm, y_mid, 3.9 * cm, bh, "Pores / trous", ["vision classique", "(black-hat)"], cv)
    for cx in (1.95 * cm, 6.1 * cm, 10.25 * cm, 14.4 * cm):
        arrow(10.15 * cm, y_top - 2, cx, y_mid + bh + 2)

    y_bot = 0.1 * cm
    box(4.2 * cm, y_bot, 8 * cm, bh, "5. Scores 0-100 + rapport", ["image annotée, JSON (écran, MQTT, historique)",
                                                                  "+ capteurs ESP32 (température, humidité)"], light)
    for cx in (1.95 * cm, 6.1 * cm, 10.25 * cm, 14.4 * cm):
        arrow(cx, y_mid - 2, 8.2 * cm, y_bot + bh + 2)
    return d


def wiring_diagram():
    """Schéma de câblage ESP32 : modules à gauche/droite, fils colorés vers les broches."""
    Wd, Hd = 16.4 * cm, 10.2 * cm
    d = Drawing(Wd, Hd)
    RED, BLACK = colors.HexColor("#dd3333"), colors.HexColor("#222222")
    C_SDA, C_SCL = colors.HexColor("#1f77b4"), colors.HexColor("#ff9f1c")
    C_DHT, C_R, C_G, C_B = colors.HexColor("#8e44ad"), colors.HexColor("#e74c3c"), colors.HexColor("#27ae60"), colors.HexColor("#2e86de")

    # Carte ESP32 au centre
    ex, ey, ew, eh = 6.3 * cm, 1.2 * cm, 3.8 * cm, 7.6 * cm
    d.add(Rect(ex, ey, ew, eh, rx=6, ry=6, fillColor=colors.HexColor("#1d2433"), strokeColor=INK))
    d.add(String(ex + ew / 2, ey + eh - 16, "ESP32", fontName="Body-Bold", fontSize=11,
                 fillColor=colors.white, textAnchor="middle"))
    d.add(String(ex + ew / 2, ey + 8, "USB-C → Raspberry Pi", fontName="Body", fontSize=7,
                 fillColor=colors.white, textAnchor="middle"))
    pins_l = {"3V3": 7.6, "GND": 7.0, "GPIO21 (SDA)": 6.2, "GPIO22 (SCL)": 5.6, "GPIO4": 4.4}
    pins_r = {"GPIO25": 6.2, "GPIO26": 5.6, "GPIO27": 5.0, "GND ": 3.8}
    for name, y in pins_l.items():
        d.add(Rect(ex - 3, y * cm - 3, 6, 6, fillColor=colors.HexColor("#c9a227"), strokeColor=None))
        d.add(String(ex + 6, y * cm - 3, name, fontName="Mono", fontSize=7, fillColor=colors.white))
    for name, y in pins_r.items():
        d.add(Rect(ex + ew - 3, y * cm - 3, 6, 6, fillColor=colors.HexColor("#c9a227"), strokeColor=None))
        d.add(String(ex + ew - 6, y * cm - 3, name.strip(), fontName="Mono", fontSize=7,
                     fillColor=colors.white, textAnchor="end"))

    def module(x, y, w, h, title, sub, pins):
        d.add(Rect(x, y, w, h, rx=4, ry=4, fillColor=colors.HexColor("#eef3f9"), strokeColor=ACCENT))
        d.add(String(x + 6, y + h - 12, title, fontName="Body-Bold", fontSize=8.5, fillColor=INK))
        d.add(String(x + 6, y + h - 22, sub, fontName="Body", fontSize=6.8, fillColor=MUTED))
        out = {}
        for i, pn in enumerate(pins):
            py = y + h - 34 - i * 9
            d.add(String(x + w - 5, py - 2, pn, fontName="Mono", fontSize=6.5, fillColor=INK, textAnchor="end"))
            out[pn] = (x + w, py)
        return out

    from reportlab.graphics.shapes import Circle
    lanes = {"3V3": 4.15, "GND": 4.55, "SDA": 4.95, "SCL": 5.35, "DATA": 5.75}   # couloir vertical par signal (cm)

    def wire(a, b, col, lane):
        """Pin du module -> couloir du signal -> broche de l'ESP32 (pas de fils superposés)."""
        x0, y0 = a
        x1, y1 = b
        xl = lanes[lane] * cm
        for seg in ((x0, y0, xl, y0), (xl, y0, xl, y1), (xl, y1, x1, y1)):
            d.add(Line(*seg, strokeColor=col, strokeWidth=1.3))
        d.add(Circle(xl, y0, 1.8, fillColor=col, strokeColor=None))

    mlx = module(0.1 * cm, 7.0 * cm, 3.6 * cm, 2.6 * cm, "MLX90614 (GY-906)", "température IR · I2C 0x5A",
                 ["VIN", "GND", "SDA", "SCL"])
    tof = module(0.1 * cm, 3.9 * cm, 3.6 * cm, 2.6 * cm, "VL53L0X / VL53L1X", "distance · I2C 0x29",
                 ["VIN", "GND", "SDA", "SCL"])
    dht = module(0.1 * cm, 1.2 * cm, 3.6 * cm, 2.2 * cm, "DHT22", "air : temp. + humidité",
                 ["+", "-", "DATA"])
    L = lambda n: (ex, pins_l[n] * cm)
    R = lambda n: (ex + ew, pins_r[n] * cm)
    for m in (mlx, tof):
        wire(m["VIN"], L("3V3"), RED, "3V3")
        wire(m["GND"], L("GND"), BLACK, "GND")
        wire(m["SDA"], L("GPIO21 (SDA)"), C_SDA, "SDA")
        wire(m["SCL"], L("GPIO22 (SCL)"), C_SCL, "SCL")
    wire(dht["+"], L("3V3"), RED, "3V3")
    wire(dht["-"], L("GND"), BLACK, "GND")
    wire(dht["DATA"], L("GPIO4"), C_DHT, "DATA")

    # LED RGB à droite, avec résistances de 220 ohms
    lx, ly, lh = 13.0 * cm, 3.3 * cm, 4.3 * cm
    d.add(Rect(lx, ly, 3.2 * cm, lh, rx=4, ry=4, fillColor=colors.HexColor("#eef3f9"), strokeColor=ACCENT))
    d.add(String(lx + 6, ly + lh - 12, "LED RGB simple", fontName="Body-Bold", fontSize=8.5, fillColor=INK))
    d.add(String(lx + 6, ly + lh - 22, "cathode commune → GND", fontName="Body", fontSize=6.8, fillColor=MUTED))
    for name, col, y in (("R", C_R, 6.2), ("G", C_G, 5.6), ("B", C_B, 5.0)):
        x0 = ex + ew
        d.add(Line(x0, y * cm, 11.2 * cm, y * cm, strokeColor=col, strokeWidth=1.3))
        d.add(Rect(11.2 * cm, y * cm - 3, 0.9 * cm, 6, fillColor=colors.HexColor("#d9c7a3"), strokeColor=INK, strokeWidth=0.5))
        d.add(String(11.65 * cm, y * cm + 5, "220 Ω", fontName="Body", fontSize=5.8, fillColor=MUTED, textAnchor="middle"))
        d.add(Line(12.1 * cm, y * cm, lx, y * cm, strokeColor=col, strokeWidth=1.3))
        d.add(String(lx + 6, y * cm - 3, name, fontName="Mono-Bold", fontSize=7.5, fillColor=col))
    d.add(String(lx + 6, 3.8 * cm - 3, "commun", fontName="Mono", fontSize=7, fillColor=INK))
    d.add(Line(ex + ew, 3.8 * cm, lx, 3.8 * cm, strokeColor=BLACK, strokeWidth=1.3))
    return d


def on_page(canv, doc):
    canv.saveState()
    canv.setFont("Body", 8)
    canv.setFillColor(MUTED)
    if doc.page > 1:
        canv.drawString(2.3 * cm, 1.3 * cm, "Smart Skin Analyzer : guide de réalisation du module d'analyse du visage")
        canv.drawRightString(A4[0] - 2.3 * cm, 1.3 * cm, f"{doc.page}")
        canv.setStrokeColor(RULE)
        canv.line(2.3 * cm, 1.65 * cm, A4[0] - 2.3 * cm, 1.65 * cm)
    canv.restoreState()


def load_metrics():
    acne, wr = None, None
    runs = sorted((RUNS / "acne").glob("*/test_metrics.json"), key=lambda f: f.stat().st_mtime)         if (RUNS / "acne").exists() else []
    for f in runs:
        if f.parent.name != "essai":            # les essais rapides ne sont pas des résultats
            acne = json.loads(f.read_text())
    f = RUNS / "wrinkles" / "test_metrics.json"
    if f.exists():
        wr = json.loads(f.read_text())
    # Sur un autre appareil (pas de D:/skin_ai/runs) : copie versionnée dans docs/resultats
    res = HERE / "resultats"
    if acne is None and (res / "acne_test_metrics.json").exists():
        acne = json.loads((res / "acne_test_metrics.json").read_text())
    if wr is None and (res / "rides_test_metrics.json").exists():
        wr = json.loads((res / "rides_test_metrics.json").read_text())
    return acne, wr


# =============================================================================
# CONTENU
# =============================================================================
def build():
    acne_m, wr_m = load_metrics()

    # ---- Page de titre ------------------------------------------------------
    story.append(Spacer(1, 5 * cm))
    story.append(Paragraph("Smart Skin Analyzer", S["title"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Module d'analyse du visage par intelligence artificielle", S["subtitle"]))
    story.append(Paragraph("Acné · Rides · Taches · Pores", S["subtitle"]))
    story.append(Spacer(1, 1.2 * cm))
    story.append(Paragraph("Guide de réalisation et explication détaillée des scripts", S["meta"]))
    story.append(Paragraph("Projet IoT : miroir intelligent (Raspberry Pi 4 + ESP32 + caméra)", S["meta"]))
    story.append(Spacer(1, 3 * cm))
    story.append(Paragraph(f"Version du {date.today().strftime('%d/%m/%Y')}", S["meta"]))

    # ---- Sommaire ----------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("Sommaire", S["toctitle"]))
    toc = TableOfContents()
    toc.levelStyles = [S["toc1"], S["toc2"]]
    story.append(toc)
    story.append(PageBreak())

    # ---- 1. Objectif -------------------------------------------------------
    h1("1. Objectif et vue d'ensemble")
    p("Ce module est la partie « intelligence » du miroir intelligent <b>Smart Skin Analyzer</b>. "
      "À partir d'une image du visage prise par la caméra du miroir, il détecte et mesure quatre "
      "critères visibles de l'état de la peau, puis produit un score et un rapport exploitables par "
      "l'interface du miroir et par la partie IoT.")
    table([
        ["Critère", "Ce qui est mesuré", "Méthode retenue"],
        ["Acné", "Boutons (papules, pustules, comédons) : nombre, position, taille",
         "<b>Apprentissage profond</b> : détecteur YOLO11 entraîné sur ACNE04"],
        ["Rides", "Rides et ridules : masque au pixel près, longueur par zone",
         "<b>Apprentissage profond</b> : segmentation U-Net entraînée sur FFHQ-Wrinkle"],
        ["Taches", "Taches pigmentaires (zones plus sombres, non rouges) : % de surface",
         "Vision par ordinateur classique (contraste local dans l'espace L*a*b*)"],
        ["Pores / trous", "Pores dilatés, points noirs, petites cicatrices : densité par cm²",
         "Vision par ordinateur classique (transformée morphologique black-hat)"],
    ], [2.6, 6.6, 7.2])
    p("Le développement s'est fait en <b>deux phases</b> :")
    bullets([
        "<b>Phase 1 : prototype en vision classique.</b> Les quatre critères sont détectés par des "
        "règles de traitement d'image, sans entraînement. Cette phase a mis en place toute la chaîne "
        "(caméra, points du visage, zones, scores, affichage) et sert de solution de secours.",
        "<b>Phase 2 : modèles d'apprentissage profond.</b> Pour l'acné et les rides, deux vrais modèles "
        "sont entraînés sur des bases publiques annotées par des humains, puis évalués sur des images "
        "jamais vues pendant l'entraînement.",
    ])
    h2("1.1 Architecture du pipeline")
    story.append(pipeline_diagram())
    story.append(Paragraph("Figure 1 : chaîne de traitement complète. En vert, les modèles "
                           "d'apprentissage profond ; en orange, la vision classique.", S["caption"]))
    h2("1.2 Lien avec le matériel du projet")
    table([
        ["Matériel", "Rôle pour ce module"],
        ["Raspberry Pi 4", "Exécute l'analyse (modèles au format ONNX lus par OpenCV) et l'interface"],
        ["Caméra Pi / webcam HD", "Fournit l'image du visage ; 1080p recommandé pour les pores"],
        ["VL53L0X (distance)", "Déclencher l'analyse quand le visage est à la bonne distance (≈ 30-40 cm)"],
        ["Bande LED / LED RGB", "Éclairage frontal uniforme : réduit les ombres prises pour des taches"],
        ["MLX90614, DHT22 (ESP32)", "Mesures complémentaires ajoutées au rapport (hors de ce module)"],
    ], [4.5, 11.9])

    # ---- 2. Environnement ---------------------------------------------------
    h1("2. Environnement de travail")
    h2("2.1 Organisation des dossiers")
    p("Tout le projet est sur le disque <b>D:</b>. Le disque C: était presque plein (1,9 Go libres) "
      "et l'ancien dossier se trouvait dans OneDrive, qui aurait synchronisé des dizaines de Go de "
      "photos vers le cloud.")
    code(r"""
D:\skin_ai\
├── code\                      ← code source (à ouvrir dans VS Code)
│   ├── skin_analyzer\         ← module d'analyse (utilisé par le miroir)
│   │   ├── config.py          ← tous les paramètres réglables
│   │   ├── face_regions.py    ← points du visage + zones de peau
│   │   ├── detectors.py       ← détecteurs classiques (acné, rides, taches, pores)
│   │   ├── dl_models.py       ← inférence des modèles profonds (ONNX)
│   │   ├── analyzer.py        ← orchestration + scores + contrôle qualité
│   │   ├── visualize.py       ← image annotée + panneau de scores
│   │   ├── main.py            ← programme en ligne de commande (photo / webcam)
│   │   └── models\            ← modèles (points du visage, YOLO, U-Net)
│   ├── training\              ← scripts d'entraînement
│   │   ├── paths.py, download_data.py
│   │   ├── prepare_acne_data.py, train_acne.py
│   │   ├── train_wrinkles.py
│   │   ├── wsl_setup.sh, wsl_train.sh   ← installation / lancement sous Ubuntu
│   │   ├── wsl_queue.sh       ← enchaîne les rides après l'acné
│   │   └── status.py          ← avancement des entraînements
│   ├── status.bat             ← double-clic : état des entraînements
│   ├── tests\test_synthetic.py
│   └── docs\                  ← ce guide
├── datasets\                  ← bases (ACNE04, FFHQ-Wrinkle)
├── runs\                      ← résultats d'entraînement (courbes, poids, scores)
└── wsl\                       ← disque virtuel d'Ubuntu (PyTorch, copie des données)
""")
    h2("2.2 Logiciels")
    table([
        ["Élément", "Version / choix", "Justification"],
        ["Python", "3.11", "Même version que Raspberry Pi OS (Bookworm) : le code tourne à l'identique sur le Pi"],
        ["OpenCV (contrib)", "5.0", "Traitement d'image, détection de visage YuNet, points LBF, lecture des modèles ONNX"],
        ["MediaPipe", "1.0", "478 points du visage (moteur principal, sur le Pi)"],
        ["PyTorch + CUDA 12.6", "2.x (sous WSL2)", "Entraînement sur la carte graphique NVIDIA RTX 2070 (8 Go)"],
        ["Ubuntu 24.04 (WSL2)", "Python 3.12", "Environnement Linux d'entraînement, non concerné par Smart App Control"],
        ["Ultralytics", "8.x", "Entraînement YOLO11 (détection de l'acné)"],
        ["segmentation-models-pytorch", "0.5", "Architecture U-Net avec encodeur pré-entraîné ImageNet"],
        ["albumentations", "2.x", "Augmentation de données pour la segmentation"],
    ], [4.2, 2.8, 9.4])
    h2("2.3 Problèmes rencontrés et solutions")
    table([
        ["Problème", "Cause", "Solution"],
        ["MediaPipe refuse de se charger (WinError 4551)",
         "Windows Smart App Control bloque sa DLL non signée",
         "Second moteur de points 100 % OpenCV (YuNet + Facemark LBF, 68 points), choisi automatiquement. "
         "Sur le Raspberry Pi, MediaPipe fonctionne."],
        ["Disque C: plein", "1,9 Go libres ; PyTorch ≈ 5 Go, bases ≈ 20 Go",
         "Tout déplacé vers D:\\skin_ai ; cache pip purgé (1,4 Go)"],
        ["Projet dans OneDrive", "Synchronisation des Go de données vers le cloud",
         "Données hors OneDrive (D:\\skin_ai\\datasets)"],
        ["Base FFHQ complète = 65 Go", "Les 70 000 photos ne sont pas toutes utiles",
         "Téléchargement image par image des seules photos annotées (miroir Hugging Face)"],
        ["PyTorch refuse de se charger (WinError 4551 sur c10.dll)",
         "Même cause : Smart App Control (état « activé » dans le registre)",
         "<b>Solution retenue :</b> entraînement sous Ubuntu 24.04 via WSL2, installé sur D:. "
         "Smart App Control reste actif sous Windows, et la RTX 2070 reste accessible depuis Linux"],
    ], [4.3, 4.6, 7.5])
    h2("2.4 Installation")
    p("Deux environnements Python coexistent :")
    bullets([
        "<b>Windows</b> (venv du projet) : application d'analyse, préparation des données, génération de ce guide. "
        "Pas de PyTorch nécessaire : les modèles entraînés sont lus par OpenCV.",
        "<b>Ubuntu 24.04 sous WSL2</b> (nommé <font name='Mono'>skinai</font>, stocké dans D:\\skin_ai\\wsl) : "
        "entraînement des modèles avec PyTorch et la carte graphique. Les données y sont copiées "
        "(/data/skin_ai/datasets) pour une lecture rapide ; les résultats sont écrits sur D: (D:\\skin_ai\\runs).",
    ])
    code(r"""
:: 1. Installer Ubuntu sur D: (une seule fois, depuis PowerShell)
wsl --install -d Ubuntu-24.04 --location D:\skin_ai\wsl --name skinai --no-launch

:: 2. Installer PyTorch (CUDA 12.6), YOLO, U-Net... dans Ubuntu
wsl -d skinai -u root -- bash /mnt/d/skin_ai/code/training/wsl_setup.sh

:: 3. Copier les données dans le disque Linux (lecture plus rapide)
wsl -d skinai -u root -- rsync -a /mnt/d/skin_ai/datasets/acne_yolo /data/skin_ai/datasets/
wsl -d skinai -u root -- rsync -a /mnt/d/skin_ai/datasets/ffhq_wrinkle /data/skin_ai/datasets/

:: 4. Vérifier la carte graphique sous Linux
wsl -d skinai -u root -- nvidia-smi
""")
    p("Le script <font name='Mono'>training/wsl_train.sh</font> règle les variables d'environnement "
      "(emplacement des données, des résultats et des caches) puis lance l'entraînement demandé.")

    # ---- 3. Phase 1 -------------------------------------------------------
    h1("3. Phase 1 : module d'analyse (vision classique)")
    p("Cette phase construit toute la chaîne d'analyse. Elle reste utile après la phase 2 : "
      "les modèles profonds remplacent seulement les détecteurs d'acné et de rides, et la "
      "localisation du visage, les zones, les scores et l'affichage restent les mêmes.")

    h2("3.1 config.py : paramètres")
    p("Tous les seuils sont regroupés dans un seul fichier pour faciliter la calibration. "
      "Idée clé : <b>toutes les tailles sont exprimées dans une image normalisée</b> où la distance "
      "entre les coins externes des yeux vaut 400 px (≈ 90 mm sur un adulte, soit ≈ 4,4 px/mm). "
      "Les seuils ne dépendent donc pas de la distance entre le visage et la caméra.")
    table([
        ["Paramètre", "Valeur", "Rôle"],
        ["NORM_EYE_DIST / EYE_DIST_MM", "400 px / 90 mm", "Échelle commune : conversion pixels → millimètres"],
        ["SKIN_COLOR_TOLERANCE", "16", "Écart de couleur Lab max. avec la peau des joues (rejette cheveux, fond)"],
        ["MIN_EYE_DIST_RAW", "140 px", "En dessous : visage trop loin, avertissement"],
        ["ACNE_RED_DELTA", "7", "Excès de rougeur a* par rapport à la peau voisine"],
        ["WRINKLE_THRESHOLD", "0,035", "Réponse minimale du filtre de crêtes"],
        ["SPOT_DARK_DELTA", "9", "Assombrissement L* minimal d'une tache"],
        ["PORE_THRESHOLD", "12", "Contraste minimal d'un pore (niveaux de gris)"],
        ["SCORE_SCALE", "par critère", "Échelle de conversion mesure → score 0-100"],
    ], [5.2, 2.8, 8.4])

    h2("3.2 face_regions.py : points du visage et zones de peau")
    h3("Deux moteurs de points")
    bullets([
        "<b>MediaPipe Face Landmarker</b> : 478 points en 3D, très précis. Moteur principal, utilisé sur le Raspberry Pi.",
        "<b>OpenCV YuNet + Facemark LBF</b> : YuNet (réseau léger, 230 Ko) trouve le visage, puis LBF place "
        "68 points (schéma iBUG : mâchoire 0-16, sourcils 17-26, nez 27-35, yeux 36-47, bouche 48-67). Moteur de secours.",
    ])
    p("La fonction <font name='Mono'>make_backend()</font> essaie MediaPipe et bascule automatiquement sur OpenCV "
      "en cas d'erreur. Chaque moteur décrit ses zones par des listes d'indices de points (dictionnaires "
      "<font name='Mono'>MEDIAPIPE_LAYOUT</font> et <font name='Mono'>LBF68_LAYOUT</font>) : le reste du code ne dépend pas du moteur.")
    h3("Étapes de extract()")
    bullets([
        "<b>1. Recadrage</b> autour des points, avec une marge plus grande en haut pour le front.",
        "<b>2. Mise à l'échelle</b> pour que la distance entre les yeux vaille 400 px.",
        "<b>3. Zones</b> : front, joue gauche/droite, nez, menton (polygones de points, enveloppe convexe) "
        "et pattes d'oie (rectangle orienté construit à partir du coin externe de l'œil). Avec 68 points, "
        "le front n'a pas de points : il est extrapolé au-dessus des sourcils, sur 0,4 × la distance entre les yeux.",
        "<b>4. Exclusions</b> : yeux, sourcils et lèvres (élargis de quelques pixels) sont retirés de toutes les zones.",
        "<b>5. Masque couleur de peau</b> : la couleur médiane des joues sert de référence ; tout pixel trop éloigné "
        "dans l'espace L*a*b* (cheveux, frange, fond) est retiré. La luminance L* compte pour moitié, "
        "pour tolérer les variations d'éclairage.",
    ])
    code("""
def _skin_color_mask(img, reference):
    lab = cv2.cvtColor(cv2.GaussianBlur(img, (0, 0), 2), cv2.COLOR_BGR2LAB).astype(np.float32)
    ref = np.median(lab[reference > 0], axis=0)      # couleur typique des joues
    diff = lab - ref
    diff[..., 0] *= 0.5                              # tolérance sur la luminosité
    dist = np.sqrt((diff ** 2).sum(axis=2))
    return (dist < config.SKIN_COLOR_TOLERANCE)      # True = pixel de peau
""")

    h2("3.3 detectors.py : les quatre détecteurs classiques")
    callout("Principe commun : chaque pixel est comparé à la <b>peau voisine</b>, et non à un seuil absolu. "
            "La peau voisine est estimée par un flou gaussien calculé uniquement sur les pixels de peau "
            "(fonction <font name='Mono'>masked_blur</font> = flou(canal × masque) / flou(masque)). "
            "La détection devient ainsi peu sensible à l'éclairage global et à la carnation.",
            title="Comparaison locale")
    h3("Acné : detect_acne()")
    bullets([
        "Canal <b>a*</b> (axe vert-rouge de L*a*b*) : un bouton est plus rouge que la peau autour.",
        "Δa = a*(lissé) − a*(peau voisine, σ = 6 mm) ; pixels retenus si Δa &gt; 7.",
        "Ouverture morphologique (supprime le bruit), puis contours ; filtres : surface entre 1,5 et 60 mm², "
        "circularité 4πA/P² ≥ 0,35.",
        "Sortie : nombre de lésions, position, rayon, rougeur moyenne, zone.",
    ])
    h3("Rides : detect_wrinkles()")
    bullets([
        "Luminance relative = L / L(peau voisine) : vaut 1 sur une peau uniforme, moins dans un sillon.",
        "<b>Filtre de crêtes de Sato</b> (valeurs propres de la matrice hessienne, échelles σ = 1,5 ; 2,5 ; 3,5 px) : "
        "réagit aux structures fines, sombres et allongées.",
        "Une bande au bord de chaque zone est ignorée (effet de bord, cheveux).",
        "Composantes connexes conservées si longueur du squelette ≥ 4 mm et allongement ≥ 3.",
        "Mesure : mm de rides par cm² de zone (front + pattes d'oie).",
    ])
    h3("Taches : detect_spots()")
    bullets([
        "Assombrissement ΔL = L(peau voisine, σ = 8 mm) − L(lissé) &gt; 9, <b>sans</b> excès de rouge (Δa &lt; 6), "
        "ce qui distingue une tache pigmentaire d'un bouton.",
        "Surface entre 2 et 150 mm², allongement ≤ 4 (sinon c'est plutôt une ride ou une ombre).",
        "Mesure : pourcentage de surface de peau couverte.",
    ])
    h3("Pores / trous : detect_pores()")
    bullets([
        "<b>Transformée black-hat</b> (fermeture − image, disque de 9 px) : fait ressortir les petits points "
        "plus sombres que leur entourage.",
        "Points conservés : de 3 px à 1,2 mm², à peu près ronds ; zones joues et nez.",
        "Mesure : pores par cm². Un pore situé dans un bouton ou une tache n'est pas compté deux fois "
        "(fonction <font name='Mono'>_drop_pores_inside_lesions</font> de analyzer.py).",
    ])
    h3("Conversion en score")
    p("Chaque mesure brute v devient un score de sévérité de 0 à 100 par une saturation progressive : "
      "<b>score = 100 × (1 − e<super>−v / échelle</super>)</b>. Niveaux : faible (&lt; 25), modéré (&lt; 55), élevé. "
      "Le score global de peau vaut 100 − (0,35·acné + 0,25·rides + 0,20·taches + 0,20·pores).")

    h2("3.4 analyzer.py, visualize.py, main.py")
    bullets([
        "<b>analyzer.py</b> : classe <font name='Mono'>SkinAnalyzer</font> ; méthode <font name='Mono'>analyze(image)</font> "
        "qui renvoie le rapport et les zones. Contrôle qualité : distance entre les yeux, luminosité "
        "moyenne de la peau, netteté (variance du Laplacien). <font name='Mono'>report_to_json()</font> "
        "retire les données lourdes pour l'envoi (MQTT, serveur web).",
        "<b>visualize.py</b> : dessine les zones, les boutons (cercles rouges), les taches (rectangles orange), "
        "les rides (surlignées en bleu) et les pores (points jaunes), plus un panneau latéral de scores.",
        "<b>main.py</b> : programme en ligne de commande, sur une photo ou en direct avec la webcam "
        "(ESPACE = analyser, Z = zones, Q = quitter). Les résultats sont enregistrés dans results/.",
    ])
    code(r"""
python -m skin_analyzer.main --image photo.jpg
python -m skin_analyzer.main --camera 0
python -m skin_analyzer.main --camera 0 --backend opencv
""")
    figure("astronaut_analyse.jpg", "Figure 2 : analyse classique d'une photo libre de droits "
           "(zones en gris, taches en orange, panneau de scores à droite).", 13)

    h2("3.5 tests/test_synthetic.py : test par injection")
    p("Faute de photos annotées pour la vision classique, on <b>dessine de faux défauts</b> de taille réaliste "
      "sur un vrai visage, puis on vérifie que chaque détecteur les retrouve à leur position :")
    bullets([
        "6 disques rouges de ≈ 3 mm sur les joues (acné) ;",
        "3 disques brun foncé de ≈ 5 mm (taches), espacés des boutons ;",
        "3 lignes sombres sur le front et les pattes d'oie (rides) ;",
        "25 petits points sombres sur le nez (pores).",
    ])
    table([
        ["Critère", "Défauts retrouvés", "Résultat"],
        ["Acné", "100 % (6/6)", "OK"],
        ["Taches", "100 % (3/3)", "OK"],
        ["Pores", "100 % (25/25)", "OK"],
        ["Rides", "64 % des pixels de rides dessinés", "OK (seuil 60 %)"],
    ], [4, 7, 5.4])
    figure("test_injection.jpg", "Figure 3 : test par injection ; les défauts dessinés sont tous retrouvés.", 13)
    callout("Ce test prouve que les détecteurs fonctionnent comme prévu, mais <b>pas</b> qu'ils sont précis sur "
            "de vraies lésions. C'est la raison de la phase 2 : de vrais modèles évalués sur de vraies "
            "annotations humaines.", WARN, "Limite")

    # ---- 4. Phase 2 : données ---------------------------------------------
    h1("4. Phase 2 : bases de données d'apprentissage")
    h2("4.1 Bases étudiées et choix")
    table([
        ["Base", "Contenu", "Décision"],
        ["<b>ACNE04</b><br/>Wu et al., ICCV 2019",
         "1 457 photos de visages, <b>18 983 lésions</b> d'acné annotées en boîtes par des dermatologues ; "
         "4 niveaux de sévérité",
         "<b>Retenue pour l'acné.</b> Base de référence de la littérature ; usage académique libre"],
        ["<b>FFHQ-Wrinkle</b><br/>Moon et al., ICPR 2024",
         "1 000 masques de rides tracés à la main + 50 000 masques « faibles » automatiques, "
         "sur les photos FFHQ 1024×1024",
         "<b>Retenue pour les rides.</b> Première base publique de segmentation des rides du visage entier ; CC BY-NC-SA 4.0"],
        ["Skin-Problem-Detection<br/>(Roboflow)",
         "2 660 images, 10 classes (acné, taches, pores, rides...)",
         "Écartée : images de 255×255 px (pores invisibles), annotations incohérentes "
         "(« Eyebags » encadrant tout le visage, rides en grosses boîtes)"],
    ], [3.6, 7.0, 5.8])
    figure("apercu_rides.jpg", "Figure 4 : exemples FFHQ-Wrinkle ; à droite, les rides annotées à la main "
           "(en rouge). Elles couvrent en moyenne 0,7 % des pixels.", 7.5)

    h2("4.2 training/download_data.py")
    bullets([
        "<b>ACNE04</b> : téléchargement du dossier Google Drive officiel avec <font name='Mono'>gdown</font>, "
        "puis extraction des archives Classification.tar (photos) et Detection.tar (annotations VOC XML).",
        "<b>FFHQ-Wrinkle</b> : masques manuels et masques faibles depuis Google Drive ; les photos FFHQ "
        "correspondantes sont prises une par une sur le miroir Hugging Face <font name='Mono'>marcosv/ffhq-dataset</font> "
        "(dossier Part{numéro // 10000 + 1}), avec 8 téléchargements en parallèle et reprise automatique.",
        "Variables : <font name='Mono'>SKIN_AI_DIR</font> (défaut D:/skin_ai) et <font name='Mono'>N_WEAK</font> "
        "(nombre d'images pour le pré-entraînement, défaut 10 000, soit ≈ 13 Go).",
    ])
    code(r"""
cd /d D:\skin_ai\code
..\venv\Scripts\python -m training.download_data acne
..\venv\Scripts\python -m training.download_data wrinkles
""")

    # ---- 5. Acné ----------------------------------------------------------
    h1("5. Modèle d'acné : YOLO11 sur ACNE04")
    h2("5.1 prepare_acne_data.py : préparation en tuiles")
    p("Dans ACNE04, un bouton ne mesure que 0,5 à 2 % de la largeur de la photo. Si l'on réduit toute la "
      "photo à 1024 px, les plus petits ne font plus que quelques pixels et deviennent indétectables. "
      "La solution est le <b>découpage en tuiles</b> :")
    bullets([
        "tuiles de 1024×1024 px à la <b>résolution d'origine</b>, chevauchement de 25 % ;",
        "une boîte est gardée dans une tuile si au moins 50 % de sa surface y est visible ;",
        "30 % des tuiles sans bouton sont conservées comme <b>exemples négatifs</b> (limite les fausses détections) ;",
        "la photo entière réduite à 1024 px est ajoutée (contexte global du visage).",
    ])
    p("Résultat obtenu (photos de 3112×3456 à 5184×3456 px) :")
    table([
        ["Partie", "Photos", "Lésions annotées", "Tuiles générées", "Boîtes dans les tuiles"],
        ["Entraînement", "1 166", "14 813", "12 369", "42 042"],
        ["Validation", "146", "2 007", "1 569", "5 723"],
        ["Test", "145", "2 163", "1 508", "5 883"],
    ], [3.2, 2.4, 3.4, 3.4, 4.0])
    p("Il y a plus de boîtes que de lésions parce qu'une même lésion apparaît dans plusieurs tuiles "
      "qui se chevauchent, et dans la photo entière réduite.")
    callout("Le découpage train / validation / test (80 / 10 / 10 %) se fait <b>par photo, avant le découpage "
            "en tuiles</b>. Deux tuiles d'une même photo ne peuvent donc jamais se retrouver l'une en "
            "entraînement et l'autre en test, ce qui gonflerait artificiellement les scores.",
            OK, "Point méthodologique important")

    h2("5.2 train_acne.py : entraînement")
    table([
        ["Hyperparamètre", "Valeur", "Justification"],
        ["Modèle", "YOLO11s (9,4 M param.)", "Seule taille qui tient en 1024 px avec un lot raisonnable sur 8 Go (voir 5.3)"],
        ["Poids initiaux", "pré-entraînés COCO", "Apprentissage par transfert : convergence plus rapide, meilleure précision"],
        ["Taille d'entrée", "1024 px", "Préserve les petites lésions"],
        ["Epochs / patience", "150 / 40", "Entraînement long, arrêt automatique sans progrès pendant 40 epochs"],
        ["Optimiseur", "AdamW, lr 0,001, cosinus", "Stable ; décroissance douce du taux d'apprentissage"],
        ["Batch", "8 images (≈ 5 Go)", "Mesuré sur la RTX 2070 ; précision mixte (AMP) ; gradients accumulés jusqu'à 64"],
        ["Augmentation couleur", "HSV h 0,015 · s 0,5 · v 0,4", "Robustesse à l'éclairage et à la caméra du miroir"],
        ["Augmentation géométrique", "rotation ±10°, échelle ±50 %, miroir", "Pose et distance variables"],
        ["Mosaic / mixup", "1,0 / 0,1 ; arrêt mosaic 15 dernières epochs", "Plus d'exemples variés, fin d'entraînement sur images réalistes"],
    ], [4, 4.6, 7.8])
    p("En fin d'entraînement, le script évalue automatiquement le meilleur modèle sur la <b>partie test</b> "
      "(photos jamais vues), enregistre les scores dans <font name='Mono'>test_metrics.json</font>, "
      "puis exporte le modèle en ONNX vers <font name='Mono'>skin_analyzer/models/acne_yolo.onnx</font>.")
    code(r"""
python -m training.prepare_acne_data                    :: sous Windows
set T=wsl -d skinai -u root -- bash /mnt/d/skin_ai/code/training/wsl_train.sh
%T% acne --epochs 3 --name essai                        :: essai rapide
%T% acne                                                :: entraînement complet
%T% acne --resume                                       :: reprise après coupure
""")
    h2("5.3 Choix de la taille du modèle : mesures réelles")
    p("Le premier choix était YOLO11m, plus gros et en principe plus précis. L'essai a montré qu'il ne "
      "tenait pas dans les 8 Go de la RTX 2070 en 1024 px. On a alors privilégié la résolution, "
      "indispensable pour des boutons de quelques pixels, plutôt que la taille du réseau :")
    table([
        ["Configuration (1024 px)", "Mémoire GPU", "Vitesse", "Durée estimée (150 epochs)", "Décision"],
        ["YOLO11m, lot de 2", "6,8 Go", "≈ 26 min / epoch", "≈ 65 h", "Écartée (trop long)"],
        ["YOLO11m, lot de 4+", "&gt; 8 Go", "-", "-", "Impossible (mémoire saturée)"],
        ["<b>YOLO11s, lot de 8</b>", "<b>≈ 5 Go</b>", "<b>≈ 6 min / epoch</b>", "<b>≈ 15 h max</b>", "<b>Retenue</b>"],
    ], [3.8, 2.4, 2.8, 3.6, 3.8])
    p("Réduire l'image à 640 px pour garder YOLO11m aurait fait perdre les plus petites lésions : à "
      "résolution égale, un modèle plus petit détecte mieux ce qu'il voit qu'un modèle plus gros qui "
      "ne voit plus les détails.")
    h2("5.4 Métriques d'évaluation")
    table([
        ["Métrique", "Définition", "Lecture"],
        ["Précision", "VP / (VP + FP)", "Parmi les boutons détectés, part de vrais boutons"],
        ["Rappel", "VP / (VP + FN)", "Parmi les vrais boutons, part de boutons trouvés"],
        ["mAP@50", "Aire sous la courbe précision-rappel, IoU ≥ 0,5", "Métrique principale en détection"],
        ["mAP@50-95", "Moyenne des mAP pour IoU de 0,5 à 0,95", "Exige des boîtes très bien placées"],
    ], [3, 6.4, 7])
    if acne_m:
        table([["Résultat sur le test ACNE04 (145 photos jamais vues)", "Valeur"]] +
              [[k, f"{v:.3f}"] for k, v in acne_m.items()], [8, 8.4])
        figure("acne_courbes.png", "Figure 5 : courbes d'entraînement YOLO11s. Les métriques de validation "
               "plafonnent vers l'epoch 60 ; l'arrêt automatique intervient à l'epoch 115.", 15)
        figure("acne_pred.jpg", "Figure 6 : prédictions sur le test (confiance affichée ≥ 0,25). "
               "Le modèle trouve les lésions les plus nettes mais en manque beaucoup sur les acnés sévères.", 14)
        callout("Le score est en dessous de ce qui était espéré (mAP@50 ≈ 0,4-0,6). Les confiances ne "
                "dépassent jamais 0,5 : le modèle hésite, signe d'annotations difficiles (lésions minuscules et "
                "très denses). Le seuil de confiance de l'application est fixé à <b>0,16</b>, valeur qui maximise "
                "le F1 sur la <b>validation</b> (0,41). Le test mélange tuiles et photos entières réduites, alors "
                "que l'application n'utilise que des tuiles : le score réel en utilisation est probablement un peu "
                "meilleur. Pistes d'amélioration : retirer les photos réduites de l'entraînement, tuiles plus "
                "petites agrandies.", WARN, "Analyse du résultat")
        p("<b>Évaluation par photo, dans l'application</b> (analyse complète par tuiles, comme sur le miroir) : "
          "sur les 125 photos de test où un visage est détecté (21 profils trop marqués sont rejetés), le nombre "
          "de boutons détectés suit le nombre annoté avec une <b>corrélation de 0,75</b>, mais le modèle en trouve "
          "environ la moitié (6,1 en moyenne contre 11,5 annotés ; erreur moyenne de 6 boutons). Le classement "
          "des niveaux de sévérité est donc fiable, mais pas le compte exact : l'échelle du score d'acné en tient "
          "compte (3,5 boutons détectés au lieu de 6).")
    else:
        callout("Les scores seront ajoutés automatiquement ici après l'entraînement (relancer "
                "<font name='Mono'>python docs/build_guide.py</font>). Ordre de grandeur attendu d'après la "
                "littérature : mAP@50 ≈ 0,4 à 0,6. Les lésions sont minuscules et l'accord entre "
                "dermatologues est lui-même imparfait.", WARN, "Résultats : entraînement en cours")

    # ---- 6. Rides -----------------------------------------------------------
    h1("6. Modèle de rides : U-Net sur FFHQ-Wrinkle")
    h2("6.1 Pourquoi la segmentation ?")
    p("Une ride est une ligne fine et souvent courbe : une boîte englobante la décrit très mal. La "
      "<b>segmentation sémantique</b> prédit, pour chaque pixel, la probabilité qu'il appartienne à une ride. "
      "On obtient la forme exacte, d'où l'on déduit la longueur et la densité par zone.")
    h2("6.2 train_wrinkles.py : méthode en deux étapes")
    p("La méthode reprend celle de l'article FFHQ-Wrinkle :")
    bullets([
        "<b>Étape 1, pré-entraînement</b> sur les masques « faibles » (≈ 10 000 images, 8 epochs, lr 3·10<super>-4</super>). "
        "Ces masques, générés automatiquement à partir de cartes de texture, sont imparfaits, mais leur "
        "nombre apprend au réseau ce qu'est une texture de ride.",
        "<b>Étape 2, ajustement fin</b> sur les 800 masques manuels d'entraînement (120 epochs, lr 10<super>-4</super>), "
        "avec évaluation sur la validation toutes les 2 epochs et sauvegarde du meilleur modèle (IoU maximale).",
    ])
    table([
        ["Choix", "Valeur", "Justification"],
        ["Architecture", "U-Net, encodeur ResNet-50 (ImageNet)", "Connexions de saut : conserve les détails fins ; encodeur pré-entraîné"],
        ["Résolution", "crops de 512 px pris dans des images de 1024 px", "Pas de réduction : une ride fait 3 à 6 px de large"],
        ["Échantillonnage", "1 recadrage sur 2 centré sur une zone contenant des rides", "Les rides étant rares (0,7 % des pixels), le réseau en voit assez"],
        ["Perte", "Dice + 2 × Focal (α 0,75 ; γ 2)", "Adaptée aux classes très déséquilibrées (0,7 % de pixels)"],
        ["Augmentation", "miroir, rotation ±12°, échelle ±25 %, luminosité, teinte, bruit, JPEG, flou",
         "Robustesse à la caméra et à l'éclairage du miroir"],
        ["Optimisation", "AdamW + OneCycle, précision mixte", "Convergence rapide et stable sur 8 Go"],
        ["Test-time augmentation", "moyenne image + image miroir", "Prédiction plus stable"],
    ], [3.4, 5.6, 7.4])
    callout("Les 1 000 masques manuels sont répartis une fois pour toutes en 800 / 100 / 100 (fichier "
            "<font name='Mono'>split.json</font>, graine fixe). Le <b>seuil de décision</b> est choisi sur la "
            "validation, puis appliqué tel quel au test. Le test n'influence donc aucun choix et les "
            "scores obtenus sont honnêtes.", OK, "Protocole d'évaluation")
    p("La perte combine deux termes. <b>Dice</b> = 1 − 2|P∩G| / (|P| + |G|) mesure le chevauchement global "
      "entre prédiction P et vérité G, sans être dominée par le fond. <b>Focal</b> = −α(1−p)<super>γ</super>log(p) "
      "donne plus de poids aux pixels difficiles (bords de rides, ridules).")
    code(r"""
%T% wrinkles                       :: étapes 1 + 2 + test
%T% wrinkles --stage finetune      :: étape 2 seule
%T% wrinkles --stage test          :: évaluation seule
""")
    h2("6.3 Métriques")
    table([
        ["Métrique", "Définition"],
        ["IoU (indice de Jaccard, JSI)", "VP / (VP + FP + FN), calculé sur tous les pixels du test"],
        ["F1 (Dice)", "2·VP / (2·VP + FP + FN)"],
        ["Précision / rappel", "au niveau du pixel"],
    ], [6, 10.4])
    if wr_m:
        table([["Résultat sur le test FFHQ-Wrinkle (100 visages jamais vus)", "Valeur"]] +
              [[k, f"{v}"] for k, v in wr_m.items()], [8, 8.4])
        figure("rides_resultat.jpg", "Figure 7 : à gauche les rides annotées à la main (rouge), à droite les "
               "rides prédites par le modèle exporté, exécuté dans l'application (OpenCV, alignement FFHQ).", 11)
        callout("L'étape 1 (masques faibles) donne une IoU quasi nulle sur les masques manuels : les deux types "
                "d'annotations sont très différents. L'ajustement fin fait ensuite monter l'IoU de validation de "
                "0,29 (epoch 4) à 0,49 (epoch 112). Dans l'application, l'IoU par image est un peu plus basse "
                "(≈ 0,37) car le recadrage refait à partir des points du visage décale les traits d'un ou deux "
                "pixels, ce qui pèse lourd pour des lignes aussi fines. Temps de calcul : ≈ 3,3 s par visage sur "
                "le processeur du PC (deux passages, image + miroir).", OK, "Analyse du résultat")
        p("<b>Étalonnage du score :</b> sur les 100 visages de test, l'application mesure en médiane 0,9 mm de "
          "rides par cm² de visage (25 % : 0,58 ; 75 % : 1,31 ; 90 % : 2,32). L'échelle du score est fixée à 2,1 : "
          "un visage médian obtient 35 (modéré), les 10 % les plus ridés dépassent 65 (élevé).")
    else:
        callout("Les scores seront ajoutés automatiquement après l'entraînement. Note : pour des structures "
                "aussi fines, un décalage d'un ou deux pixels compte comme une erreur. Des IoU autour de "
                "0,3 à 0,5 sont donc typiques dans la littérature, même pour de bons modèles.",
                WARN, "Résultats : entraînement en attente des données")

    # ---- 7. Intégration -----------------------------------------------------
    h1("7. Intégration dans le miroir : dl_models.py")
    p("Les modèles entraînés sont exportés au format <b>ONNX</b> et lus par <b>OpenCV DNN</b>. Il n'y a "
      "aucune dépendance supplémentaire, que ce soit sur le PC Windows ou sur le Raspberry Pi.")
    h2("7.1 Rides : alignement FFHQ")
    p("Le modèle de rides a été entraîné sur des visages cadrés d'une manière bien précise (alignement "
      "FFHQ). À l'utilisation, on reproduit <b>exactement le même cadrage</b> : un quadrilatère est calculé à "
      "partir du centre des yeux et des coins de la bouche, puis le visage est redressé en 1024×1024 "
      "par une transformation affine. Le masque prédit est ensuite ramené dans l'image d'origine "
      "par la transformation inverse.")
    code("""
eye_avg = (eye_l + eye_r) / 2 ;  eye_to_eye = eye_r - eye_l
eye_to_mouth = (mouth_l + mouth_r) / 2 - eye_avg
x = eye_to_eye - flipud(eye_to_mouth) * [-1, 1]
x = x / |x| * max(2.0 * |eye_to_eye|, 1.8 * |eye_to_mouth|)
y = flipud(x) * [-1, 1] ;  c = eye_avg + 0.1 * eye_to_mouth
quad = [c - x - y, c - x + y, c + x + y, c + x - y]      # même formule que NVlabs
""")
    h2("7.2 Acné : inférence par tuiles")
    bullets([
        "Comme à l'entraînement, l'image est parcourue par tuiles de 1024 px qui se chevauchent "
        "(ajout de bordure grise pour les tuiles incomplètes).",
        "Sortie YOLO décodée : (cx, cy, w, h, score) pour chaque candidat.",
        "Les boîtes de toutes les tuiles sont fusionnées par <b>suppression des non-maxima</b> (NMS, IoU 0,45), "
        "ce qui retire les doublons dans les zones de chevauchement.",
        "Seules les détections dont le centre tombe sur la peau (zones du visage) sont gardées.",
    ])

    # ---- 8. Procédure -------------------------------------------------------
    h1("8. Procédure complète pas à pas")
    table([
        ["#", "Étape", "Commande (depuis D:\\skin_ai\\code)", "Durée indicative"],
        ["1", "Installer Ubuntu (WSL2) + PyTorch", "voir section 2.4", "20-30 min"],
        ["2", "Télécharger ACNE04 (Windows)", "python -m training.download_data acne", "10-20 min"],
        ["3", "Télécharger FFHQ-Wrinkle (Windows)", "python -m training.download_data wrinkles", "1-4 h (≈ 22 Go)"],
        ["4", "Préparer les tuiles d'acné (Windows)", "python -m training.prepare_acne_data", "≈ 5 min"],
        ["5", "Copier les données dans Ubuntu", "voir section 2.4, étape 3", "≈ 15 min"],
        ["6", "Essai rapide YOLO (Ubuntu)", "%T% acne --epochs 3 --name essai", "≈ 20 min"],
        ["7", "Entraîner l'acné (Ubuntu)", "%T% acne", "≈ 6-12 h (RTX 2070)"],
        ["8", "Entraîner les rides (Ubuntu)", "%T% wrinkles", "≈ 8-14 h (RTX 2070)"],
        ["9", "Tester sur une photo (Windows)", "python -m skin_analyzer.main --image photo.jpg", "secondes"],
        ["10", "Mettre ce guide à jour (Windows)", "python docs\\build_guide.py", "secondes"],
    ], [0.7, 4.6, 7.6, 3.5])
    p("<font name='Mono'>%T%</font> désigne <font name='Mono'>wsl -d skinai -u root -- bash "
      "/mnt/d/skin_ai/code/training/wsl_train.sh</font>. Les commandes Windows se lancent depuis "
      "D:\\skin_ai\\code avec l'environnement Python du projet.")
    h2("8.1 Lancer et suivre un entraînement long")
    bullets([
        "Chaque entraînement est lancé dans <b>sa propre fenêtre</b> (ne pas la fermer). Le script "
        "<font name='Mono'>wsl_queue.sh</font> attend la fin de l'acné puis démarre les rides tout seul, "
        "car la carte graphique ne peut pas faire les deux à la fois.",
        "<b>status.bat</b> (double-clic) affiche pour chaque modèle : état (pas démarré / EN COURS / "
        "TERMINÉ / ARRÊTÉ ?), epoch en cours, temps restant estimé, meilleur score de validation, "
        "puis les scores sur le test une fois terminé.",
        "Journaux complets : <font name='Mono'>D:\\skin_ai\\runs\\acne_train.log</font> et "
        "<font name='Mono'>wrinkles_train.log</font> ; la dernière ligne <font name='Mono'>=== Fin ... code=0</font> "
        "signifie succès.",
        "Le fichier <font name='Mono'>test_metrics.json</font> n'apparaît qu'à la toute fin : sa présence "
        "indique que l'entraînement est terminé.",
        "Le PC ne doit pas se mettre en veille pendant l'entraînement.",
    ])
    callout("Les courbes d'apprentissage (perte, précision, rappel, mAP), la matrice de confusion et des "
            "exemples de prédictions sont générés automatiquement dans <font name='Mono'>D:\\skin_ai\\runs\\</font>. "
            "Ce sont de bonnes figures pour le rapport.", ACCENT, "Pour le rapport")

    # ---- 9. Matériel ----------------------------------------------------------
    h1("9. Partie matérielle : miroir, ESP32 et Raspberry Pi")
    p("Le miroir réunit deux cartes aux rôles bien séparés : l'<b>ESP32</b> s'occupe des capteurs et de "
      "la LED (temps réel, électronique), le <b>Raspberry Pi 4</b> de la caméra, de l'analyse IA, de "
      "l'affichage et de l'historique. Ils communiquent par le câble USB-C, qui alimente aussi l'ESP32.")
    h2("9.1 Rôle de chaque composant")
    table([
        ["Composant", "Rôle", "Connexion"],
        ["Raspberry Pi 4", "Caméra, analyse (modèles ONNX), interface, historique", "Alimentation 5 V / 3 A"],
        ["Pi Camera Module 3", "Photo du visage 12 MP, mise au point automatique", "Nappe CSI du Pi"],
        ["Écran HDMI 5\" (800×480)", "Interface sur fond noir, derrière le miroir", "HDMI du Pi"],
        ["ESP32", "Lit les capteurs, pilote la LED, envoie du JSON 5 fois/s", "USB-C → USB du Pi"],
        ["VL53L0X / VL53L1X", "Distance du visage : déclenche et guide l'analyse", "I2C (GPIO21/22)"],
        ["MLX90614", "Température de la peau sans contact", "I2C (GPIO21/22)"],
        ["DHT22", "Température et humidité de l'air (conseils d'hydratation)", "GPIO4"],
        ["LED RGB", "État du miroir : attente, détection, analyse, OK, erreur", "GPIO25/26/27 + 220 Ω"],
    ], [4.2, 7.8, 4.4])

    h2("9.2 Carte retenue : Arduino Uno + capteur Sharp IR")
    p("La partie capteurs a été réalisée par J. Salek (dépôt <font name='Mono'>jihanesalek263-png/"
      "SmartSkinAnalyzer</font>) sur un <b>Arduino Uno</b> avec un capteur de distance <b>Sharp GP2Y0A21</b> "
      "(analogique, 10-80 cm). C'est la carte retenue pour le miroir. Le firmware "
      "<font name='Mono'>firmware/uno_capteurs/uno_capteurs.ino</font> reprend le sien avec le <b>même format "
      "JSON</b>, en ajoutant un envoi 4 fois par seconde (au lieu de toutes les 2 s, pour guider la personne en "
      "direct) et le pilotage de la LED RGB. Le miroir reconnaît automatiquement l'Uno ou l'ESP32.")
    table([
        ["Module", "Broche module", "Broche Arduino Uno", "Remarque"],
        ["MLX90614", "VIN / GND", "3.3V / GND", "jamais 5 V sur un capteur nu"],
        ["MLX90614", "SDA / SCL", "A4 / A5", "bus I2C de l'Uno"],
        ["DHT22", "patte 1 / 2 / 4", "5V / D2 / GND", "résistance 10 kΩ entre les pattes 1 et 2"],
        ["Sharp GP2Y0A21", "rouge / noir / jaune", "5V / GND / A0", "distance par la tension analogique"],
        ["LED RGB", "R / G / B", "D9 / D10 / D11", "220 Ω sur chaque couleur ; patte commune au GND"],
    ], [3.4, 3.6, 3.4, 6.0])
    p("Le firmware compile pour l'Uno (40 % de la mémoire programme, 34 % de la RAM). Message envoyé : "
      "<font name='Mono'>{\"distance_cm\":18.3,\"temp_peau\":33.4,\"temp_air\":24.1,\"humidite\":46.2}</font>.")

    h2("9.2 bis Variante : câblage de l'ESP32")
    story.append(wiring_diagram())
    story.append(Paragraph("Figure 8 : câblage. Les deux capteurs I2C partagent les mêmes fils SDA/SCL "
                           "(adresses différentes : 0x5A et 0x29).", S["caption"]))
    table([
        ["Module", "Broche module", "Broche ESP32", "Remarque"],
        ["MLX90614, VL53L0X", "VIN / GND", "3V3 / GND", "les modules GY acceptent 3,3 V"],
        ["MLX90614, VL53L0X", "SDA / SCL", "GPIO21 / GPIO22", "bus I2C partagé, 100 kHz"],
        ["DHT22", "+ / - / DATA", "3V3 / GND / GPIO4", "résistance 10 kΩ DATA→3V3 si capteur nu (pas sur module)"],
        ["LED RGB", "R / G / B", "GPIO25 / 26 / 27", "une résistance de 220 Ω sur chaque couleur"],
        ["LED RGB", "patte commune (la plus longue)", "GND (ou 3V3)", "si 3V3 : mettre LED_ANODE_COMMUNE à 1 dans le firmware"],
    ], [3.4, 3.6, 3.4, 6.0])

    h2("9.3 Montage du miroir")
    bullets([
        "<b>Écran derrière le miroir sans tain</b> (ou vitre + film miroir). L'interface utilise un fond "
        "<b>noir</b> : le noir n'émet pas de lumière, cette zone reste un miroir, et seuls les textes clairs "
        "apparaissent à travers.",
        "<b>Caméra</b> en haut, au centre, à hauteur des yeux. Un miroir sans tain laisse passer ≈ 30 % de la "
        "lumière : découper un petit trou dans le film en face de l'objectif donne des photos bien plus nettes.",
        "<b>Capteurs VL53L0X et MLX90614 jamais derrière le verre</b> : le verre est opaque à l'infrarouge "
        "thermique (MLX90614) et le capteur de distance mesurerait le verre. Les placer dans le cadre, face à "
        "l'utilisateur, à côté de la caméra.",
        "<b>MLX90614 :</b> le modèle courant (GY-906 « BAA ») voit sous un angle de 90°. À 40 cm il mesure la "
        "moyenne d'une large zone (visage, cheveux, fond) : la valeur est plus basse que la vraie température de "
        "la peau. La version « DCI » (angle de 5°) est plus juste à distance.",
        "<b>Éclairage :</b> la LED indique l'état. Pour la qualité des photos, un éclairage frontal diffus "
        "(bande LED blanche autour du miroir) réduit les ombres prises pour des taches.",
        "<b>DHT22</b> à l'air libre, loin de l'écran et du Pi qui chauffent.",
    ])

    h2("9.4 Firmware de l'ESP32 (firmware/esp32_capteurs.ino)")
    bullets([
        "IDE Arduino → <i>Préférences</i> → URL de cartes : "
        "<font name='Mono'>https://espressif.github.io/arduino-esp32/package_esp32_index.json</font>, puis "
        "<i>Gestionnaire de cartes</i> → installer <b>esp32 by Espressif</b> (version 3.x).",
        "<i>Gestionnaire de bibliothèques</i> : <b>Adafruit MLX90614 Library</b>, <b>DHT sensor library</b> "
        "(+ Adafruit Unified Sensor), <b>VL53L0X</b> et <b>VL53L1X</b> (Pololu).",
        "Carte : <b>ESP32 Dev Module</b> ; choisir le port COM ; Téléverser. Au démarrage, la LED affiche "
        "rouge, vert puis bleu : c'est le test de câblage.",
        "Le firmware détecte seul le VL53L0X ou le VL53L1X et continue de fonctionner si un capteur manque "
        "(valeur <font name='Mono'>null</font>).",
    ])
    table([
        ["Sens", "Message", "Exemple"],
        ["ESP32 → Pi", "mesure (5 fois/s)", '{"type":"mesure","dist_mm":412,"t_visage":34.8,"t_air":23.6,"humidite":41.2}'],
        ["ESP32 → Pi", "présentation", '{"type":"hello","capteurs":{"mlx":true,"tof":"VL53L0X","dht":true}}'],
        ["Pi → ESP32", "état de la LED", "ETAT ANALYSE   (attente, detecte, analyse, ok, erreur, eteint)"],
        ["Pi → ESP32", "couleur libre", "LED 255 0 0"],
    ], [2.4, 3.2, 10.8])

    h2("9.5 Installation du Raspberry Pi")
    bullets([
        "<b>Raspberry Pi Imager</b> (sur le PC) : appareil <i>Raspberry Pi 4</i>, système <i>Raspberry Pi OS "
        "(64-bit)</i> avec bureau, carte microSD. Dans les réglages : nom d'hôte <font name='Mono'>skinmirror</font>, "
        "utilisateur et mot de passe, WiFi, et <b>activer SSH</b>. Écrire la carte.",
        "Brancher caméra (nappe CSI, Pi éteint), écran HDMI, ESP32 (USB), puis l'alimentation.",
        "Copier le projet depuis le PC : <font name='Mono'>scp -r D:\\skin_ai\\code skinmirror.local:~/skin_ai</font> "
        "(ou une clé USB). Les modèles sont dans <font name='Mono'>skin_analyzer/models</font> (≈ 230 Mo).",
        "Sur le Pi : <font name='Mono'>cd ~/skin_ai &amp;&amp; bash deploy/setup_pi.sh</font> puis "
        "<font name='Mono'>sudo reboot</font>. Le miroir se lance ensuite tout seul à chaque démarrage.",
    ])

    h2("9.6 Programme du miroir (mirror/)")
    table([
        ["Fichier", "Rôle"],
        ["app.py", "Machine à états : attente → guidage → compte à rebours → photo → température de près → "
                   "analyse → résultats"],
        ["skin_type.py", "Type de peau (sèche, normale, mixte, grasse) : règles de J. Salek, affiché « indicatif »"],
        ["esp32.py", "Lecture des mesures dans un thread, reconnexion automatique, commandes de LED"],
        ["camera.py", "Pi Camera Module 3 (picamera2, mise au point avant la photo), webcam ou photo de test"],
        ["ui.py", "Écrans sur fond noir (horloge, guidage par la distance, 3-2-1, analyse, résultats)"],
        ["routine.py", "Conseils simples selon les scores, l'humidité de l'air et la température de la peau"],
        ["history.py", "Historique (historique.jsonl) et évolution par rapport à l'analyse précédente"],
        ["config.py", "Plage de distance (30-48 cm), durées, résolution, rotation de la caméra"],
    ], [3, 13.4])
    figure("miroir_ecrans.png", "Figure 9 : écrans du miroir, capturés en mode test (personne simulée, "
           "analyse d'une photo ACNE04 par les deux modèles profonds).", 16)

    h2("9.6 bis Température de la peau : mesure en 2 temps")
    p("Le MLX90614 n'est fiable qu'entre 10 et 30 cm : plus loin, il voit aussi le décor et sous-estime la "
      "température. La photo, elle, se prend à 30-48 cm pour cadrer tout le visage. Le miroir procède donc en "
      "deux temps : après la photo, il affiche « Approchez-vous à 20 cm » avec une jauge de distance, fait "
      "4 lectures de température dans la zone fiable et garde la <b>médiane</b>, pendant que l'analyse IA de la "
      "photo continue en arrière-plan (aucun temps perdu). Sans lecture fiable au bout de 12 s, la dernière "
      "valeur est gardée et le type de peau est marqué « peu fiable ».")
    callout("Le type de peau repose sur des <b>règles fixées à la main</b> (et non sur un modèle entraîné : le jeu "
            "de données d'origine est généré par ces mêmes règles). De plus, le DHT22 mesure l'humidité de "
            "l'<b>air</b>, pas l'hydratation de la peau. Le résultat est donc affiché comme une estimation "
            "indicative ; une vraie mesure d'hydratation demanderait un capteur capacitif au contact.",
            WARN, "Limite du type de peau")

    h2("9.7 Mise en service, étape par étape")
    table([
        ["#", "Test", "Commande", "Résultat attendu"],
        ["1", "ESP32 seul (sur le PC ou le Pi)", "python tools/test_esp32.py",
         "distance qui varie quand on bouge la main ; températures plausibles ; LED qui change de couleur"],
        ["2", "Caméra du Pi", "rpicam-still -o test.jpg", "photo nette du visage"],
        ["3", "Miroir sans capteurs", "python -m mirror.app --sim --windowed", "P = personne, ESPACE = analyse"],
        ["4", "Miroir complet", "bash deploy/start_mirror.sh", "s'approcher : guidage, 3-2-1, analyse, résultats"],
    ], [0.6, 3.6, 5.2, 7.0])
    callout("Le firmware a été compilé et le programme du miroir testé de bout en bout en simulation "
            "(sans matériel). Restent à vérifier sur le vrai matériel : les valeurs des capteurs, la "
            "netteté de la caméra derrière le miroir, et le <b>temps d'analyse sur le Raspberry Pi 4</b> "
            "(≈ 5 s sur le PC ; nettement plus sur le Pi : si c'est trop lent, passer WRINKLE_TTA à False "
            "dans skin_analyzer/config.py divise par deux le temps du modèle de rides).",
            WARN, "Ce qui reste à valider sur le matériel")

    # ---- 10. Limites --------------------------------------------------------
    h1("10. Limites, éthique et suite du projet")
    h2("10.1 Limites")
    bullets([
        "<b>Écart de domaine.</b> Les photos ACNE04 et FFHQ ne sont pas prises par la caméra du miroir. "
        "La précision réelle doit être vérifiée sur quelques photos du miroir, avec le même éclairage.",
        "<b>Taches et pores</b> restent en vision classique, faute de base publique fiable : leurs seuils "
        "doivent être calibrés sur des photos réelles du miroir.",
        "<b>Les pores</b> ne sont visibles qu'avec une bonne résolution (≥ 1080p, à 30-40 cm, lumière diffuse).",
        "<b>Biais.</b> La répartition des carnations, des âges et des types de peau dans les bases influence les "
        "performances ; à vérifier sur des volontaires variés.",
    ])
    h2("10.2 Éthique et licences")
    bullets([
        "Ce système donne une <b>indication cosmétique</b>, pas un diagnostic médical.",
        "Photos de volontaires : consentement écrit, données anonymisées, stockage local.",
        "ACNE04 : usage académique uniquement (citer Wu et al., ICCV 2019).",
        "FFHQ-Wrinkle : CC BY-NC-SA 4.0, usage non commercial (citer Moon et al., ICPR 2024).",
    ])
    h2("10.3 Prochaines étapes")
    bullets([
        "Mesurer le temps d'analyse sur le Raspberry Pi 4 et l'optimiser si besoin (sans double passage, "
        "export NCNN de YOLO, modèle de rides plus léger).",
        "Calibrer les seuils des taches et des pores sur des photos prises par la caméra du miroir.",
        "Améliorer le modèle d'acné (version 2 : sans photos réduites, tuiles agrandies).",
        "Option IoT : publier le rapport JSON en MQTT pour un tableau de bord sur téléphone.",
    ])
    h2("10.4 Références")
    for ref in [
        "X. Wu et al., « Joint Acne Image Grading and Counting via Label Distribution Learning », ICCV 2019. "
        "Base ACNE04 : github.com/xpwu95/LDL",
        "J. Moon et al., « Facial Wrinkle Segmentation for Cosmetic Dermatology: Pretraining with Texture "
        "Map-Based Weak Supervision », ICPR 2024. github.com/labhai/ffhq-wrinkle-dataset",
        "T. Karras et al., « A Style-Based Generator Architecture for GANs », CVPR 2019 (base FFHQ).",
        "Ultralytics YOLO11 : docs.ultralytics.com",
        "O. Ronneberger et al., « U-Net: Convolutional Networks for Biomedical Image Segmentation », MICCAI 2015.",
        "Y. Sato et al., « Three-dimensional multi-scale line filter for segmentation and visualization of "
        "curvilinear structures in medical images », Medical Image Analysis, 1998.",
        "Google MediaPipe Face Landmarker ; OpenCV YuNet et Facemark LBF.",
    ]:
        story.append(Paragraph(ref, S["ref"], bulletText="–"))

    doc = Doc(str(OUT), pagesize=A4, leftMargin=2.3 * cm, rightMargin=2.3 * cm,
              topMargin=2 * cm, bottomMargin=2.2 * cm,
              title="Smart Skin Analyzer - Guide de réalisation", author="Projet IoT")
    doc.multiBuild(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"PDF généré : {OUT}")


if __name__ == "__main__":
    build()
