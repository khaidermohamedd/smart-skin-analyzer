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
RESULT_S = 15                      # durée d'affichage des résultats (s)

# --- Caméra (Pi Camera Module 3) ---------------------------------------------
CAPTURE_SIZE = (4608, 2592)        # pleine résolution pour l'analyse
PREVIEW_SIZE = (1280, 720)         # aperçu temps réel affiché sur le miroir
LIVE_PREVIEW = True                # afficher la caméra en direct (attente, guidage, 3-2-1)
BURST_N = 5                        # photos prises à la suite ; la plus nette est analysée
BURST_INTERVAL_S = 0.15
MAX_EXPOSURE_US = 25000            # pose max des photos (1/40 s) : moins de flou ; le gain compense
AF_FACE_EVERY_S = 0.5              # fréquence de recalage de la mise au point sur le visage
CAMERA_ROTATION = 0                # 0 ou 180 selon le montage
MIRROR_IMAGE = True                # retourner horizontalement (effet miroir)

# --- Historique -------------------------------------------------------------
HISTORY_DIR = Path.home() / "skin_history"
SAVE_PHOTOS = True                 # ne garder les photos que si les volontaires l'acceptent

# --- Déclenchement à distance -------------------------------------------------
TRIGGER_FILE = Path("/tmp/skin_mirror_analyse")   # si ce fichier apparaît, une analyse démarre
SHUTDOWN_HOLD_S = 3                # Échap maintenu ce temps (s) = extinction du Raspberry Pi
