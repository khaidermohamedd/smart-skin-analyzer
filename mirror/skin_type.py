"""Type de peau estimé à partir des capteurs (température de la peau + humidité).

Règles reprises telles quelles du dépôt de J. Salek :
https://github.com/jihanesalek263-png/SmartSkinAnalyzer (classification_peau.py)

ATTENTION : ce sont des règles fixées à la main, pas un modèle entraîné, et l'humidité vient du
DHT22, qui mesure l'humidité de l'AIR et non l'hydratation de la peau. Le résultat est donc
affiché comme une estimation indicative. Une vraie mesure d'hydratation demanderait un capteur
capacitif au contact de la peau.
"""

# Le MLX90614 voit aussi le décor derrière le visage quand on s'éloigne : au-delà de ~30 cm,
# la température est sous-estimée (zone fiable reprise du dépôt d'origine).
DISTANCE_MIN_CM = 10.0
DISTANCE_MAX_CM = 30.0

LABELS = {"seche": "sèche", "normale": "normale", "mixte": "mixte", "grasse": "grasse"}


def classifier_peau(temperature, humidite):
    """Règles d'origine : renvoie 'seche', 'normale', 'mixte' ou 'grasse'."""
    if humidite < 30:
        return "seche"
    if temperature > 34:
        return "grasse" if humidite > 60 else "mixte"
    if temperature < 31 and humidite <= 60:
        return "mixte"
    return "normale"


def estimate(sensors):
    """Renvoie {'type', 'label', 'fiable', 'message'} ou None si les capteurs manquent."""
    t, h = sensors.get("t_visage"), sensors.get("humidite")
    if t is None or h is None:
        return None
    d_mm = sensors.get("dist_mm")
    d_cm = d_mm / 10 if d_mm is not None else None
    fiable = d_cm is not None and DISTANCE_MIN_CM <= d_cm <= DISTANCE_MAX_CM
    if d_cm is None and sensors.get("distance_consigne"):
        # Pas de capteur de distance : lectures prises après la consigne « 20 cm » et filtrées
        # (température plausible pour une peau proche) -> considérées comme fiables
        kind = classifier_peau(t, h)
        return {"type": kind, "label": LABELS[kind], "fiable": True,
                "message": "à ~20 cm (consigne, distance non mesurée)", "court": "à ~20 cm (consigne)"}
    if d_cm is None:
        msg, short = "distance inconnue", "distance inconnue"
    elif fiable:
        msg = short = f"mesuré à {d_cm:.0f} cm"
    else:
        msg = f"mesuré à {d_cm:.0f} cm (fiable entre 10 et 30 cm)"
        short = f"trop {'loin' if d_cm > DISTANCE_MAX_CM else 'près'} ({d_cm:.0f} cm)"
    kind = classifier_peau(t, h)
    return {"type": kind, "label": LABELS[kind], "fiable": fiable, "message": msg, "court": short}
