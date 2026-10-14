"""Paramètres réglables du module d'analyse de peau.

Toutes les tailles sont exprimées dans l'image NORMALISÉE, où la distance
entre les deux coins externes des yeux vaut NORM_EYE_DIST pixels
(~ 90 mm sur un adulte => ~ 4.4 px/mm). Ainsi les seuils ne dépendent pas
de la distance visage-caméra.

Ces valeurs sont des points de départ : à calibrer sur vos propres photos
(même éclairage, même caméra que le miroir final).
"""
from pathlib import Path

MODELS_DIR = Path(__file__).parent / "models"
MODEL_PATH = MODELS_DIR / "face_landmarker.task"          # MediaPipe (478 points)
YUNET_PATH = MODELS_DIR / "face_detection_yunet.onnx"     # secours OpenCV : détection
LBF_PATH = MODELS_DIR / "lbfmodel.yaml"                   # secours OpenCV : 68 points

# --- Normalisation géométrique -------------------------------------------
NORM_EYE_DIST = 400          # px entre coins externes des yeux après mise à l'échelle
EYE_DIST_MM = 90.0           # distance moyenne réelle (adulte) pour convertir px -> mm

# --- Masque couleur de peau ----------------------------------------------
SKIN_COLOR_TOLERANCE = 16    # écart Lab max à la couleur médiane des joues
SKIN_HOLE_MAX_PX = 40000     # trous rebouchés (boutons, taches) jusqu'à ~2000 mm² dans l'image normalisée

# --- Contrôle qualité de l'image ------------------------------------------
MIN_EYE_DIST_RAW = 140       # en dessous : visage trop loin / trop petit
MIN_BRIGHTNESS = 70          # luminance moyenne (0-255) minimale de la peau
MAX_BRIGHTNESS = 220
MIN_SHARPNESS = 40.0         # variance du Laplacien sur la peau

# --- Acné (boutons rouges) -------------------------------------------------
ACNE_RED_DELTA = 7.0         # excès de rougeur a* par rapport à la peau voisine
ACNE_MIN_AREA_MM2 = 1.5
ACNE_MAX_AREA_MM2 = 60.0
ACNE_MIN_CIRCULARITY = 0.35

# --- Rides -----------------------------------------------------------------
WRINKLE_SIGMAS = (1.5, 2.5, 3.5)   # échelles du filtre de crêtes (px)
WRINKLE_THRESHOLD = 0.035          # réponse minimale du filtre de crêtes
WRINKLE_MIN_LENGTH_MM = 4.0
WRINKLE_MIN_ELONGATION = 3.0       # longueur / largeur

# --- Taches pigmentaires ---------------------------------------------------
SPOT_DARK_DELTA = 9.0        # assombrissement L* par rapport à la peau voisine
SPOT_MAX_RED_DELTA = 6.0     # au-delà c'est plutôt de l'acné / rougeur
SPOT_MIN_AREA_MM2 = 2.0
SPOT_MAX_AREA_MM2 = 150.0

# --- Pores / petits trous --------------------------------------------------
PORE_BLACKHAT_KSIZE = 9      # taille du noyau morphologique (px)
PORE_THRESHOLD = 12          # contraste minimal (niveaux de gris)
PORE_MIN_AREA_PX = 3
PORE_MAX_AREA_MM2 = 1.2

# --- Conversion en scores 0-100 (100 = problème très marqué) ---------------
# score = 100 * (1 - exp(-valeur / echelle))  -> saturation progressive
SCORE_SCALE = {
    "acne": 6.0,        # nombre de lésions
    "rides": 25.0,      # mm de rides par cm² de zone analysée
    "taches": 3.0,      # % de surface couverte
    "pores": 12.0,      # pores par cm²
    "rides_dl": 2.1,    # mm/cm² de visage (U-Net). FFHQ test : médiane 0,9 -> score 35 ; 90e centile 2,3 -> 67
    "acne_dl": 3.5,     # boutons détectés par YOLO, qui en trouve ~la moitié (6,1 détectés pour 11,5 annotés)
}

# --- Modèles d'apprentissage profond (utilisés s'ils existent) --------------
ACNE_MODEL = MODELS_DIR / "acne_yolo.onnx"          # YOLO11 entraîné sur ACNE04
ACNE_CONF = 0.16                                     # F1 max sur la VALIDATION ACNE04 (0,41 à 0,158)
ACNE_REF_EYE_DIST = 860      # px entre coins externes des yeux, médiane des photos ACNE04 (mesurée)
USE_DL = True                # utiliser les modèles profonds s'ils sont présents
WRINKLE_TTA = True           # double passage image + miroir (plus précis, 2x plus lent)
WRINKLE_MODEL = MODELS_DIR / "wrinkle_unet.onnx"    # U-Net entraîné sur FFHQ-Wrinkle
WRINKLE_META = MODELS_DIR / "wrinkle_unet.json"
