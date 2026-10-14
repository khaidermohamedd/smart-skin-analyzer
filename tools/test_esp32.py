"""Teste l'ESP32 seul : affiche les mesures en direct et fait défiler les états de la LED.

    python tools/test_esp32.py            (port détecté automatiquement)
    python tools/test_esp32.py COM5       (Windows)   /   /dev/ttyUSB0   (Raspberry Pi)
Ctrl+C pour arrêter.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mirror.esp32 import ESP32Link, find_port  # noqa: E402


def fmt(v, unit, dec=1):
    return "   ---  " if v is None else f"{v:6.{dec}f} {unit}"


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else find_port()
    print(f"Port : {port or 'aucun trouvé (ESP32 branché ? pilote CH340/CP2102 installé ?)'}")
    link = ESP32Link(port=port)
    t0 = time.time()
    while not link.connected and time.time() - t0 < 6:
        time.sleep(0.2)
    time.sleep(1.5)
    print("Capteurs détectés :", link.info.get("capteurs", "(pas de message hello reçu)"))
    print("La LED va passer par : attente, detecte, analyse, ok, erreur (3 s chacun)\n")
    states = ["attente", "detecte", "analyse", "ok", "erreur"]
    i, t_led = 0, 0
    try:
        while True:
            if time.time() - t_led > 3:
                link.led_state(states[i % len(states)])
                i, t_led = i + 1, time.time()
            m = link.latest
            d = m.get("dist_mm")
            print(f"\rdistance {fmt(d / 10 if d else None, 'cm', 0)} | visage {fmt(m.get('t_visage'), '°C')} | "
                  f"IR amb. {fmt(m.get('t_ambiante_ir'), '°C')} | air {fmt(m.get('t_air'), '°C')} | "
                  f"humidité {fmt(m.get('humidite'), '%', 0)} | LED {states[(i - 1) % len(states)]:8s}",
                  end="", flush=True)
            time.sleep(0.2)
    except KeyboardInterrupt:
        link.led_state("eteint")
        time.sleep(0.3)
        print()


if __name__ == "__main__":
    main()
