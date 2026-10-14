"""Liaison série USB avec l'ESP32 : lecture des mesures (JSON) et commandes de LED.

La lecture tourne dans un thread : `link.latest` contient toujours la dernière mesure.
Si l'ESP32 est débranché, le thread réessaie de se connecter toutes les 2 secondes.
"""
import glob
import json
import sys
import threading
import time

from . import config


def find_port():
    if sys.platform.startswith("win"):
        from serial.tools import list_ports
        ports = [p.device for p in list_ports.comports()]
    else:
        ports = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
    return ports[0] if ports else None


class ESP32Link:
    def __init__(self, port=config.SERIAL_PORT, baud=config.SERIAL_BAUD):
        self.port, self.baud = port, baud
        self.latest = {}               # dernière mesure reçue
        self.info = {}                 # message "hello" (capteurs détectés)
        self.connected = False
        self.last_rx = 0.0
        self._ser = None
        self._lock = threading.Lock()
        self._stop = False
        threading.Thread(target=self._run, daemon=True).start()

    # -- lecture ------------------------------------------------------------
    def _run(self):
        import serial
        while not self._stop:
            try:
                port = self.port or find_port()
                if port is None:
                    raise OSError("aucun port série trouvé")
                with serial.Serial(port, self.baud, timeout=1) as ser:
                    self._ser = ser
                    self.connected = True
                    ser.write(b"INFO\n")
                    while not self._stop:
                        line = ser.readline().decode("utf-8", "ignore").strip()
                        if line.startswith("{"):
                            self._handle(line)
            except Exception:
                pass
            self.connected = False
            self._ser = None
            time.sleep(2)

    def _handle(self, line):
        try:
            msg = json.loads(line)
        except ValueError:
            return
        self.last_rx = time.time()
        if msg.get("type") == "mesure":
            self.latest = msg
        elif msg.get("type") == "hello":
            self.info = msg

    # -- accès -----------------------------------------------------------------
    @property
    def fresh(self):
        return time.time() - self.last_rx < 2.0

    def distance(self):
        return self.latest.get("dist_mm") if self.fresh else None

    def send(self, cmd):
        with self._lock:
            if self._ser is not None:
                try:
                    self._ser.write((cmd + "\n").encode())
                except Exception:
                    pass

    def led_state(self, state):
        """attente, detecte, analyse, ok, erreur, eteint"""
        self.send(f"ETAT {state.upper()}")

    def close(self):
        self._stop = True


class SimulatedLink:
    """Remplace l'ESP32 pour tester sans matériel : touches P (personne) / B (bouge)."""

    def __init__(self):
        self.connected = True
        self.info = {"firmware": "simulation", "capteurs": {"mlx": True, "tof": "simulé", "dht": True}}
        self.present = False
        self.dist = 400
        self.fresh = True
        self.led = "attente"

    @property
    def latest(self):
        return {"dist_mm": self.distance(), "t_visage": 34.6, "t_ambiante_ir": 24.0,
                "t_air": 23.5, "humidite": 38.0}

    def distance(self):
        return self.dist if self.present else None

    def led_state(self, state):
        self.led = state

    def send(self, cmd):
        pass

    def close(self):
        pass
