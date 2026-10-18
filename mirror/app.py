"""Programme principal du miroir intelligent.

    python -m mirror.app                       # sur le Raspberry Pi (ESP32 + Pi Camera)
    python -m mirror.app --sim --image photo.jpg --windowed
                                               # test sur PC, sans matériel : P = personne, ESPACE = analyse
    python -m mirror.app --sim --image photo.jpg --scenario --dump out/
                                               # test automatique sans écran (captures des écrans)

États :  ATTENTE -> GUIDAGE -> COMPTE (3,2,1) -> ANALYSE -> RÉSULTATS -> ATTENTE
"""
import argparse
import threading
import time
from pathlib import Path

import cv2

from skin_analyzer.analyzer import SkinAnalyzer, report_to_json
from skin_analyzer.visualize import annotate

from . import config, history, routine, skin_type, ui
from .camera import open_camera
from .esp32 import ESP32Link, SimulatedLink


class Mirror:
    def __init__(self, args):
        self.args = args
        self.esp = SimulatedLink() if args.sim else ESP32Link()
        self.cam = open_camera(args.image)
        print(f"[miroir] caméra : {self.cam.name}")
        print("[miroir] chargement des modèles d'analyse...")
        self.analyzer = SkinAnalyzer(args.backend)
        print(f"[miroir] modèles profonds actifs : {list(self.analyzer.dl) or 'aucun'}")
        self.state, self.t_state = None, time.time()
        self.t_good = self.t_seen = None
        self.result = self.error = None
        self.worker = None
        self.set_state("attente")
        self.dump_dir = Path(args.dump) if args.dump else None
        self.last_dumped = None

    # -------------------------------------------------------------------------
    def set_state(self, s):
        if s != self.state:
            print(f"[miroir] état : {s}")
            self.state, self.t_state = s, time.time()
            led = {"attente": "attente", "guidage": "detecte", "compte": "detecte",
                   "analyse": "analyse", "resultats": "ok", "erreur": "erreur"}[s]
            self.esp.led_state(led)

    def sensors(self):
        return dict(self.esp.latest) if self.esp.latest else {}

    def start_analysis(self):
        self.set_state("analyse")
        self.result = self.error = None
        sensors = self.sensors()

        def job():
            try:
                photo = self.cam.capture()
                report, regions = self.analyzer.analyze(photo)
                if report is None:
                    self.error = ("Visage non détecté", ["Placez-vous bien en face du miroir",
                                                         "et dégagez votre visage"])
                    return
                annotated = annotate(report, regions)
                payload = report_to_json(report)
                payload["capteurs"] = sensors
                sensors["type_peau"] = skin_type.estimate(sensors)
                payload["type_peau"] = sensors["type_peau"]
                prev = history.previous_score()
                history.save(payload, photo, annotated)
                tips = routine.advice(report, sensors)
                self.result = (report, sensors, tips, prev)
                if self.args.dump:
                    cv2.imwrite(str(Path(self.args.dump) / "analyse_annotee.jpg"), annotated)
            except Exception as e:                       # le miroir ne doit jamais planter
                self.error = ("Erreur pendant l'analyse", [str(e)[:60]])

        self.worker = threading.Thread(target=job, daemon=True)
        self.worker.start()

    # -------------------------------------------------------------------------
    def step(self):
        """Une itération : met à jour l'état et renvoie l'image à afficher."""
        now = time.time()
        dist = self.esp.distance()
        present = dist is not None and dist < config.DIST_DETECT_MM
        good = present and config.DIST_MIN_MM <= dist <= config.DIST_MAX_MM
        if present:
            self.t_seen = now
        absent_long = self.t_seen is None or now - self.t_seen > config.ABSENT_S

        s = self.state
        if s == "attente":
            if present:
                self.set_state("guidage")
            return ui.screen_idle(self.sensors(), self.esp.connected)

        if s == "guidage":
            if absent_long:
                self.set_state("attente")
            if good:
                self.t_good = self.t_good or now
                if now - self.t_good >= config.STABLE_S:
                    self.set_state("compte")
            else:
                self.t_good = None
            return ui.screen_guide(dist if present else None)

        if s == "compte":
            if not good:
                self.t_good = None
                self.set_state("guidage")
                return ui.screen_guide(dist if present else None)
            left = config.COUNTDOWN_S - int(now - self.t_state)
            if left <= 0:
                self.start_analysis()
                return ui.screen_analysis(self.t_state)
            return ui.screen_countdown(left)

        if s == "analyse":
            if self.worker and not self.worker.is_alive():
                self.set_state("resultats" if self.result else "erreur")
            return ui.screen_analysis(self.t_state)

        if s == "resultats":
            if now - self.t_state > config.RESULT_S or (absent_long and now - self.t_state > 8):
                self.set_state("attente")
            return ui.screen_results(*self.result)

        if s == "erreur":
            if now - self.t_state > 5:
                self.set_state("guidage" if present else "attente")
            return ui.screen_error(*self.error)

    # -------------------------------------------------------------------------
    def dump(self, frame):
        """Mode test : enregistre une capture à chaque nouvel état."""
        if self.dump_dir and self.state != self.last_dumped:
            self.dump_dir.mkdir(parents=True, exist_ok=True)
            n = len(list(self.dump_dir.glob("ecran_*.png")))
            cv2.imwrite(str(self.dump_dir / f"ecran_{n:02d}_{self.state}.png"), frame)
            self.last_dumped = self.state

    def scenario(self, t):
        """Mode test : une personne arrive de loin, se place, puis repart."""
        e = self.esp
        if 2 < t < 4:
            e.present, e.dist = True, 650
        elif t >= 4 and self.state not in ("resultats",):
            e.present, e.dist = True, 400
        if self.state == "resultats" and time.time() - self.t_state > 1.5:
            return False
        return t < 600

    def run(self):
        show = not self.args.dump
        if show:
            cv2.namedWindow("miroir", cv2.WINDOW_NORMAL)
            if config.FULLSCREEN and not self.args.windowed:
                cv2.setWindowProperty("miroir", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        t0 = time.time()
        try:
            while True:
                before = self.state
                frame = self.step()
                if self.state == before:          # l'image correspond bien à l'état courant
                    self.dump(frame)
                if self.args.scenario and not self.scenario(time.time() - t0):
                    break
                if show:
                    cv2.imshow("miroir", frame)
                    key = cv2.waitKey(int(1000 / config.FPS)) & 0xFF
                    if key in (ord("q"), 27):
                        break
                    if key == ord(" ") and self.state in ("attente", "guidage"):
                        self.start_analysis()
                    if key == ord("p") and isinstance(self.esp, SimulatedLink):
                        self.esp.present = not self.esp.present
                else:
                    time.sleep(1 / config.FPS)
        finally:
            self.esp.led_state("eteint")
            self.cam.close()
            self.analyzer.close()
            if show:
                cv2.destroyAllWindows()


def main():
    p = argparse.ArgumentParser(description="Miroir intelligent - analyse de la peau")
    p.add_argument("--sim", action="store_true", help="simuler l'ESP32 (pas de capteurs)")
    p.add_argument("--image", help="utiliser cette photo au lieu de la caméra")
    p.add_argument("--backend", default="auto", choices=["auto", "mediapipe", "opencv"])
    p.add_argument("--windowed", action="store_true", help="fenêtre au lieu du plein écran")
    p.add_argument("--scenario", action="store_true", help="scénario automatique (avec --sim)")
    p.add_argument("--dump", help="dossier où enregistrer les écrans (test sans affichage)")
    Mirror(p.parse_args()).run()


if __name__ == "__main__":
    main()
