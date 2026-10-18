"""Caméra : Pi Camera Module 3 (picamera2), sinon webcam OpenCV, sinon photo fixe (tests).

Deux usages :
  * preview()      : image basse résolution en continu (affichage temps réel sur le miroir)
  * capture_best() : rafale de N photos pleine résolution, on garde la plus nette (visage)
"""
import time

import cv2
import numpy as np

from skin_analyzer import config as skin_config

from . import config

_detector = None


def detect_face(bgr):
    """Rectangle (x, y, w, h) du plus grand visage, ou None (YuNet, sur une image réduite)."""
    global _detector
    h, w = bgr.shape[:2]
    s = 640 / max(h, w)
    small = cv2.resize(bgr, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    if _detector is None:
        _detector = cv2.FaceDetectorYN.create(str(skin_config.YUNET_PATH), "", (320, 320), 0.7)
    _detector.setInputSize((small.shape[1], small.shape[0]))
    _, faces = _detector.detect(small)
    if faces is None or len(faces) == 0:
        return None
    x, y, fw, fh = (max(faces, key=lambda f: f[2] * f[3])[:4] / s).astype(int)
    return max(x, 0), max(y, 0), fw, fh


def face_sharpness(bgr):
    """Netteté du VISAGE (variance du Laplacien sur le visage ramené à 400 px de large).
    0 si aucun visage : une photo sans visage n'est jamais choisie."""
    box = detect_face(bgr)
    if box is None:
        return 0.0
    x, y, fw, fh = box
    crop = bgr[y:y + fh, x:x + fw]
    if crop.size == 0:
        return 0.0
    crop = cv2.resize(crop, (400, int(400 * crop.shape[0] / crop.shape[1])), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def pick_best(frames):
    """Renvoie (meilleure photo, liste des scores de netteté)."""
    scores = [face_sharpness(f) for f in frames]
    return frames[int(np.argmax(scores))], scores


class PiCamera:
    name = "Pi Camera Module 3"

    def __init__(self):
        from picamera2 import Picamera2
        from libcamera import Transform, controls
        self.controls = controls
        self.cam = Picamera2()
        rot = config.CAMERA_ROTATION == 180
        tr = Transform(hflip=rot, vflip=rot)
        # Aperçu : champ complet du capteur, 1280x720
        self.preview_cfg = self.cam.create_preview_configuration(
            main={"size": config.PREVIEW_SIZE, "format": "RGB888"}, transform=tr)
        # Photo : pleine résolution 12 MP
        self.still_cfg = self.cam.create_still_configuration(
            main={"size": config.CAPTURE_SIZE, "format": "RGB888"}, transform=tr, buffer_count=2)
        self.cam.configure(self.preview_cfg)
        self.cam.start()
        self.sensor_w, self.sensor_h = self.cam.camera_properties["PixelArraySize"]
        self.cam.set_controls({
            "AfMode": controls.AfModeEnum.Continuous,      # mise au point continue
            "AfSpeed": controls.AfSpeedEnum.Fast,
            "AeExposureMode": controls.AeExposureModeEnum.Short,   # poses courtes en aperçu
        })
        self._t_af = 0.0
        self.last_info = {}
        time.sleep(1.0)

    # -- aperçu + mise au point sur le visage ---------------------------------
    def preview(self):
        frame = self.cam.capture_array("main")              # "RGB888" = ordre BGR pour OpenCV
        if time.time() - self._t_af > config.AF_FACE_EVERY_S:
            self._t_af = time.time()
            self._focus_on_face(frame)
        return cv2.flip(frame, 1) if config.MIRROR_IMAGE else frame

    def _focus_on_face(self, frame):
        """Dit à l'autofocus de faire le point sur le visage (et non sur le fond)."""
        box = detect_face(frame)                           # image NON retournée = repère capteur
        c = self.controls
        if box is None:
            self.cam.set_controls({"AfMetering": c.AfMeteringEnum.Auto})
            return
        x, y, w, h = box
        H, W = frame.shape[:2]
        kx, ky = self.sensor_w / W, self.sensor_h / H        # aperçu = champ complet du capteur
        win = (int(x * kx), int(y * ky), int(w * kx), int(h * ky))
        self.cam.set_controls({"AfMetering": c.AfMeteringEnum.Windows, "AfWindows": [win]})

    # -- rafale ------------------------------------------------------------------
    def capture_best(self, n=config.BURST_N):
        c = self.controls
        self.cam.autofocus_cycle()                          # mise au point (sur le visage) avant la rafale
        lens = self.cam.capture_metadata().get("LensPosition")
        self.cam.switch_mode(self.still_cfg)
        self.cam.set_controls({"AfMode": c.AfModeEnum.Manual, "LensPosition": lens,   # garder le point
                               "NoiseReductionMode": c.draft.NoiseReductionModeEnum.HighQuality})
        # Attendre que l'exposition automatique soit stable en 12 MP (sinon on lit une valeur transitoire)
        prev, t0 = None, time.time()
        while time.time() - t0 < 2.0:
            md = self.cam.capture_metadata()
            cur = md["ExposureTime"] * md["AnalogueGain"]
            if prev and abs(cur - prev) / prev < 0.05:
                break
            prev = cur
        exp, gain = md["ExposureTime"], md["AnalogueGain"]
        if exp > config.MAX_EXPOSURE_US:
            # Pose plafonnée (moins de flou de bougé), gain augmenté pour garder la luminosité
            new_gain = min(16.0, gain * exp / config.MAX_EXPOSURE_US)
            self.cam.set_controls({"ExposureTimeMode": c.ExposureTimeModeEnum.Manual,
                                   "ExposureTime": config.MAX_EXPOSURE_US,
                                   "AnalogueGainMode": c.AnalogueGainModeEnum.Manual,
                                   "AnalogueGain": new_gain})
            for _ in range(6):                              # attendre que les images suivent le réglage
                md = self.cam.capture_metadata()
                if md["ExposureTime"] <= config.MAX_EXPOSURE_US * 1.05:
                    break
        frames, metas = [], []
        for _ in range(n):
            req = self.cam.capture_request()
            f = req.make_array("main")
            metas.append(req.get_metadata())
            req.release()
            frames.append(cv2.flip(f, 1) if config.MIRROR_IMAGE else f)
            time.sleep(config.BURST_INTERVAL_S)
        # Retour à l'aperçu automatique
        self.cam.set_controls({"ExposureTimeMode": c.ExposureTimeModeEnum.Auto,
                               "AnalogueGainMode": c.AnalogueGainModeEnum.Auto,
                               "AfMode": c.AfModeEnum.Continuous})
        self.cam.switch_mode(self.preview_cfg)
        best, scores = pick_best(frames)
        m = metas[int(np.argmax(scores))]
        self.last_info = {"pose_s": f"1/{round(1e6 / m['ExposureTime'])}", "gain": round(m["AnalogueGain"], 1),
                          "mise_au_point": round(m.get("LensPosition", 0), 2), "lux": round(m.get("Lux", 0))}
        return best, scores

    def close(self):
        self.cam.stop()


class WebCamera:
    name = "Webcam (OpenCV)"

    def __init__(self, index=0):
        self.cap = cv2.VideoCapture(index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        if not self.cap.isOpened():
            raise RuntimeError("webcam introuvable")

    def _read(self):
        ok, frame = self.cap.read()
        if not ok:
            raise RuntimeError("lecture caméra impossible")
        return cv2.flip(frame, 1) if config.MIRROR_IMAGE else frame

    def preview(self):
        return self._read()

    def capture_best(self, n=config.BURST_N):
        frames = []
        for _ in range(n):
            frames.append(self._read())
            time.sleep(config.BURST_INTERVAL_S)
        return pick_best(frames)

    def close(self):
        self.cap.release()


class FileCamera:
    """Renvoie toujours la même photo : pour tester le miroir sans caméra."""
    name = "Photo de test"

    def __init__(self, path):
        self.img = cv2.imread(str(path))
        if self.img is None:
            raise RuntimeError(f"photo illisible : {path}")

    def preview(self):
        return self.img

    def capture_best(self, n=config.BURST_N):
        return self.img.copy(), [face_sharpness(self.img)]

    def close(self):
        pass


def open_camera(test_image=None):
    if test_image:
        return FileCamera(test_image)
    try:
        return PiCamera()
    except Exception as e:
        print(f"[caméra] Pi Camera indisponible ({e}) -> webcam")
        return WebCamera()
