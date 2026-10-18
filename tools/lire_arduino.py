"""Affiche les lignes brutes envoyées par l'Arduino (mesures ou diagnostic), dès son démarrage.

    python tools/lire_arduino.py              (port détecté automatiquement, 10 s)
    python tools/lire_arduino.py 30           (pendant 30 s)
Arrêter le miroir avant (le port série ne peut être ouvert que par un programme à la fois) :
    pkill -f "python -m mirror[.]app"
"""
import sys
import time
from pathlib import Path

import serial

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mirror.esp32 import find_port  # noqa: E402

duree = float(sys.argv[1]) if len(sys.argv) > 1 else 10
port = find_port()
if port is None:
    sys.exit("Aucun Arduino trouvé (câble USB branché ?)")
s = serial.Serial()
s.port, s.baudrate, s.timeout = port, 115200, 1
s.open()                       # l'ouverture redémarre l'Uno : on lit dès le début
print(f"Port {port}, lecture pendant {duree:.0f} s")
t0 = time.time()
while time.time() - t0 < duree:
    ligne = s.readline().decode("utf-8", "ignore").strip()
    if ligne:
        print(f"{time.time() - t0:5.1f}s  {ligne}", flush=True)
