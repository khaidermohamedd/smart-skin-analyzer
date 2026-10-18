"""Réglages du miroir (Raspberry Pi)."""
from pathlib import Path

# --- Écran (derrière le miroir sans tain) ---------------------------------
SCREEN_W, SCREEN_H = 800, 480      # écran HDMI 5 pouces
FULLSCREEN = True
FPS = 15

# --- Liaison ESP32 (câble USB) ---------------------------------------------
SERIAL_PORT = None                 # None = détection automatique (/dev/ttyUSB*, /dev/ttyACM*, COM*)
SERIAL_BAUD = 115200

# --- Déclenchement par le capteur de distance -------------------------------
# Carte retenue : Arduino Uno + Sharp GP2Y0A21 (portée ~10-80 cm)
DIST_DETECT_MM = 800               # quelqu'un est devant le miroir
DIST_MIN_MM = 300                  # plage idéale pour la photo
DIST_MAX_MM = 480
STABLE_S = 2.0                     # temps dans la bonne plage avant le compte à rebours
COUNTDOWN_S = 3
ABSENT_S = 4.0                     # plus personne devant depuis ... -> retour à l'attente
RESULT_S = 30                      # durée d'affichage des résultats

# --- Mesure de la température en 2 temps (le MLX90614 n'est fiable que de près) ---
TEMP_DIST_MIN_MM = 100
TEMP_DIST_MAX_MM = 300
TEMP_SAMPLES = 4                   # lectures gardées (on prend la médiane)
TEMP_SAMPLE_PERIOD_S = 0.4
TEMP_TIMEOUT_S = 12                # au-delà, on garde la dernière mesure (marquée peu fiable)

# --- Caméra (Pi Camera Module 3) ---------------------------------------------
CAPTURE_SIZE = (4608, 2592)        # pleine résolution pour l'analyse
CAMERA_ROTATION = 0                # 0 ou 180 selon le montage
MIRROR_IMAGE = True                # retourner horizontalement (effet miroir)

# --- Historique -------------------------------------------------------------
HISTORY_DIR = Path.home() / "skin_history"
SAVE_PHOTOS = False                # ne garder les photos que si les volontaires l'acceptent
