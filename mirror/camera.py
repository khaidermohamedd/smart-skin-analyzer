"""Caméra : Pi Camera Module 3 (picamera2), sinon webcam OpenCV, sinon photo fixe (tests)."""
import time

import cv2

from . import config


class PiCamera:
    name = "Pi Camera Module 3"

    def __init__(self):
        from picamera2 import Picamera2
        from libcamera import Transform, controls
        self.cam = Picamera2()
        rot = config.CAMERA_ROTATION == 180
        cfg = self.cam.create_still_configuration(
            main={"size": config.CAPTURE_SIZE, "format": "RGB888"},
            transform=Transform(hflip=rot, vflip=rot))
        self.cam.configure(cfg)
        self.cam.start()
        # Mise au point continue : le visage reste net quand la personne bouge un peu
        self.cam.set_controls({"AfMode": controls.AfModeEnum.Continuous})
        time.sleep(1.0)

    def capture(self):
        self.cam.autofocus_cycle()                       # mise au point juste avant la photo
        frame = self.cam.capture_array("main")           # format "RGB888" = BGR pour OpenCV
        return cv2.flip(frame, 1) if config.MIRROR_IMAGE else frame

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

    def capture(self):
        for _ in range(5):                               # vider les images en attente
            self.cap.read()
        ok, frame = self.cap.read()
        if not ok:
            raise RuntimeError("lecture caméra impossible")
        return cv2.flip(frame, 1) if config.MIRROR_IMAGE else frame

    def close(self):
        self.cap.release()


class FileCamera:
    """Renvoie toujours la même photo : pour tester le miroir sans caméra."""
    name = "Photo de test"

    def __init__(self, path):
        self.img = cv2.imread(str(path))
        if self.img is None:
            raise RuntimeError(f"photo illisible : {path}")

    def capture(self):
        return self.img.copy()

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
