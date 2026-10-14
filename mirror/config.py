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
DIST_DETECT_MM = 900               # quelqu'un est devant le miroir
DIST_MIN_MM = 300                  # plage idéale pour la photo
DIST_MAX_MM = 480
STABLE_S = 2.0                     # temps dans la bonne plage avant le compte à rebours
COUNTDOWN_S = 3
ABSENT_S = 4.0                     # plus personne devant depuis ... -> retour à l'attente
RESULT_S = 30                      # durée d'affichage des résultats

# --- Caméra (Pi Camera Module 3) ---------------------------------------------
CAPTURE_SIZE = (4608, 2592)        # pleine résolution pour l'analyse
CAMERA_ROTATION = 0                # 0 ou 180 selon le montage
MIRROR_IMAGE = True                # retourner horizontalement (effet miroir)

# --- Historique -------------------------------------------------------------
HISTORY_DIR = Path.home() / "skin_history"
SAVE_PHOTOS = False                # ne garder les photos que si les volontaires l'acceptent
