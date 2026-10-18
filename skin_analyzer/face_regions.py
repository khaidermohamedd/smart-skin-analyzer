"""Points du visage + construction des zones de peau.

Deux moteurs de points (choisis automatiquement) :
  * MediaPipe Face Landmarker (478 points) : le plus précis, utilisé sur le Raspberry Pi ;
  * OpenCV YuNet + Facemark LBF (68 points) : secours si MediaPipe ne peut pas
    se charger (ex. Windows Smart App Control qui bloque sa DLL).
"""
from dataclasses import dataclass, field

import cv2
import numpy as np

from . import config

# ---------------------------------------------------------------------------
# Indices des zones pour chaque moteur ("_g"/"_d" = côté gauche/droit de l'IMAGE).
# "shrink" < 1 rétrécit le polygone vers son centre (évite bords/cheveux).
MEDIAPIPE_LAYOUT = {
    "zones": {
        "front": ([21, 54, 103, 67, 109, 10, 338, 297, 332, 284, 251,
                   300, 293, 334, 296, 336, 9, 107, 66, 105, 63, 70], False, 1.0),
        "joue_g": ([116, 117, 118, 119, 100, 142, 203, 206, 216, 207, 187, 147, 123], True, 1.0),
        "joue_d": ([345, 346, 347, 348, 329, 371, 423, 426, 436, 427, 411, 376, 352], True, 1.0),
        "nez": ([168, 6, 197, 195, 5, 4, 1, 45, 275, 51, 281], True, 1.0),
        "menton": ([18, 83, 313, 201, 421, 200, 199, 175, 152, 148, 377, 176, 400], True, 1.0),
    },
    "exclude": [
        [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246],
        [263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466],
        [70, 63, 105, 66, 107, 55, 65, 52, 53, 46],
        [300, 293, 334, 296, 336, 285, 295, 282, 283, 276],
        [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185],
    ],
    "eye_g": (33, 133),      # (coin externe, coin interne)
    "eye_d": (263, 362),
    "brows": None,
    "eye_ring_g": [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246],
    "eye_ring_d": [263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466],
    "mouth": (61, 291),      # coins de la bouche (gauche, droite)
}

# Schéma iBUG 68 points : mâchoire 0-16, sourcils 17-26, nez 27-35,
# yeux 36-47, bouche 48-67.  Le front n'a pas de points : il est extrapolé.
LBF68_LAYOUT = {
    "zones": {
        "joue_g": ([1, 2, 3, 4, 48, 31, 39, 40, 41, 36], True, 0.85),
        "joue_d": ([15, 14, 13, 12, 54, 35, 42, 47, 46, 45], True, 0.85),
        "nez": ([27, 28, 29, 30, 31, 35], True, 0.9),
        "menton": ([58, 57, 56, 10, 9, 8, 7, 6], True, 0.8),
    },
    "exclude": [list(range(36, 42)), list(range(42, 48)), list(range(17, 22)),
                list(range(22, 27)), list(range(48, 60))],
    "eye_g": (36, 39),
    "eye_d": (45, 42),
    "brows": list(range(17, 27)),
    "eye_ring_g": list(range(36, 42)),
    "eye_ring_d": list(range(42, 48)),
    "mouth": (48, 54),
}

ZONES_ACNE = ["front", "joue_g", "joue_d", "nez", "menton"]
ZONES_TACHES = ["front", "joue_g", "joue_d", "nez", "menton"]
ZONES_RIDES = ["front", "patte_oie_g", "patte_oie_d"]
ZONES_PORES = ["joue_g", "joue_d", "nez"]


@dataclass
class FaceRegions:
    image: np.ndarray                 # image BGR normalisée (mise à l'échelle)
    landmarks: np.ndarray             # points en pixels de l'image normalisée
    masks: dict = field(default_factory=dict)   # nom de zone -> masque uint8 (0/255)
    skin_mask: np.ndarray = None      # union de toutes les zones
    px_per_mm: float = 1.0
    raw_eye_dist: float = 0.0         # distance entre coins externes des yeux, image d'origine
    scale: float = 1.0
    backend: str = ""
    crop: np.ndarray = None           # visage recadré, résolution d'ORIGINE (pour le modèle d'acné)
    face_mask: np.ndarray = None      # tout le visage hors yeux/sourcils/lèvres (modèle de rides)
    ffhq_points: tuple = None         # (œil g, œil d, bouche g, bouche d) pour l'alignement FFHQ


# ---------------------------------------------------------------------------
class MediaPipeBackend:
    name = "mediapipe"
    layout = MEDIAPIPE_LAYOUT

    def __init__(self):
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision
        self._mp = mp
        options = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(config.MODEL_PATH)),
            running_mode=vision.RunningMode.IMAGE,
            num_faces=1,
        )
        self._landmarker = vision.FaceLandmarker.create_from_options(options)

    def detect(self, bgr):
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        res = self._landmarker.detect(self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb))
        if not res.face_landmarks:
            return None
        h, w = bgr.shape[:2]
        return np.array([(p.x * w, p.y * h) for p in res.face_landmarks[0]], np.float32)

    def close(self):
        self._landmarker.close()


class OpenCVBackend:
    name = "opencv-lbf68"
    layout = LBF68_LAYOUT

    def __init__(self):
        self._detector = cv2.FaceDetectorYN.create(str(config.YUNET_PATH), "", (320, 320), 0.7)
        self._facemark = cv2.face.createFacemarkLBF()
        self._facemark.loadModel(str(config.LBF_PATH))

    def detect(self, bgr):
        h, w = bgr.shape[:2]
        # Détection sur une image réduite (rapide), points sur l'image complète
        s = min(1.0, 640 / max(h, w))
        small = cv2.resize(bgr, None, fx=s, fy=s) if s < 1 else bgr
        self._detector.setInputSize((small.shape[1], small.shape[0]))
        _, faces = self._detector.detect(small)
        if faces is None or len(faces) == 0:
            return None
        x, y, fw, fh = (max(faces, key=lambda f: f[2] * f[3])[:4] / s)
        ok, lms = self._facemark.fit(bgr, np.array([[x, y, fw, fh]], np.int32))
        if not ok:
            return None
        return np.asarray(lms[0], np.float32).reshape(-1, 2)

    def close(self):
        pass


def make_backend(preferred="auto"):
    if preferred in ("auto", "mediapipe"):
        try:
            return MediaPipeBackend()
        except (OSError, ImportError, RuntimeError) as e:
            if preferred == "mediapipe":
                raise
            print(f"[info] MediaPipe indisponible ({e.__class__.__name__}: {e}) -> moteur OpenCV 68 points")
    return OpenCVBackend()


# ---------------------------------------------------------------------------
class FaceRegionExtractor:
    def __init__(self, backend="auto"):
        self.backend = make_backend(backend)
        self.layout = self.backend.layout

    def close(self):
        self.backend.close()

    def detect_landmarks(self, bgr):
        """Points (N, 2) en pixels, ou None si aucun visage."""
        return self.backend.detect(bgr)

    def extract(self, bgr):
        pts = self.detect_landmarks(bgr)
        if pts is None:
            return None

        eg, ed = self.layout["eye_g"][0], self.layout["eye_d"][0]
        raw_eye_dist = float(np.linalg.norm(pts[eg] - pts[ed]))

        # Recadrage autour du visage (marge plus grande en haut pour le front)
        m = 0.25 * raw_eye_dist
        x0 = int(max(0, pts[:, 0].min() - m))
        x1 = int(min(bgr.shape[1], pts[:, 0].max() + m))
        y0 = int(max(0, pts[:, 1].min() - 2.5 * m))
        y1 = int(min(bgr.shape[0], pts[:, 1].max() + m))
        crop = bgr[y0:y1, x0:x1]
        pts = pts - np.array([x0, y0], np.float32)

        scale = config.NORM_EYE_DIST / raw_eye_dist
        interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
        img = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=interp)
        pts = pts * scale

        regions = FaceRegions(
            image=img, landmarks=pts,
            px_per_mm=config.NORM_EYE_DIST / config.EYE_DIST_MM,
            raw_eye_dist=raw_eye_dist, scale=scale, backend=self.backend.name,
            crop=crop,
        )
        L = self.layout
        regions.ffhq_points = (pts[L["eye_ring_g"]].mean(0), pts[L["eye_ring_d"]].mean(0),
                               pts[L["mouth"][0]], pts[L["mouth"][1]])
        regions.masks, regions.face_mask = self._build_masks(img, pts)
        skin = np.zeros(img.shape[:2], np.uint8)
        for m in regions.masks.values():
            skin |= m
        regions.skin_mask = skin
        return regions

    # -- construction des masques ------------------------------------------
    @staticmethod
    def _fill(shape, poly, convex=False, shrink=1.0):
        poly = np.asarray(poly, np.float32)
        if convex:
            poly = cv2.convexHull(poly).reshape(-1, 2)
        if shrink != 1.0:
            c = poly.mean(axis=0)
            poly = c + (poly - c) * shrink
        mask = np.zeros(shape, np.uint8)
        cv2.fillPoly(mask, [poly.astype(np.int32)], 255)
        return mask

    @staticmethod
    def _crow_feet(shape, pts, outer, inner):
        """Rectangle orienté à l'extérieur du coin de l'œil (pattes d'oie)."""
        o, i = pts[outer], pts[inner]
        w = np.linalg.norm(o - i)
        out = (o - i) / w
        perp = np.array([-out[1], out[0]])
        start, end = o + out * 0.15 * w, o + out * 0.85 * w
        poly = [start + perp * 0.5 * w, end + perp * 0.6 * w,
                end - perp * 0.6 * w, start - perp * 0.5 * w]
        return FaceRegionExtractor._fill(shape, poly)

    def _forehead_from_brows(self, shape, pts):
        """Front extrapolé au-dessus des sourcils (moteur 68 points)."""
        brows = pts[self.layout["brows"]]
        eye_mid = (pts[self.layout["eye_g"][0]] + pts[self.layout["eye_d"][0]]) / 2
        chin = pts[8]
        up = (eye_mid - chin) / np.linalg.norm(eye_mid - chin)
        eye_w = np.linalg.norm(pts[self.layout["eye_g"][0]] - pts[self.layout["eye_d"][0]])
        left, right = brows[0], brows[-1]
        inset = (right - left) * 0.08
        top = [right - inset + up * 0.4 * eye_w, left + inset + up * 0.4 * eye_w]
        return self._fill(shape, list(brows) + top)

    @staticmethod
    def _skin_color_mask(lab, zone):
        """Pixels de `zone` dont la couleur est proche de la peau de CETTE zone (rejette cheveux,
        barbe, fond). La référence est propre à chaque zone : un côté du visage plus éclairé
        que l'autre ne fait plus disparaître une joue entière."""
        px = lab[zone > 0]
        if len(px) < 50:
            return np.zeros(zone.shape, np.uint8)
        # Référence = pixels les plus clairs de la zone (la peau est plus claire que cheveux/barbe)
        bright = px[px[:, 0] >= np.percentile(px[:, 0], 40)]
        ref = np.median(bright, axis=0)
        diff = lab - ref
        diff[..., 0] *= config.SKIN_L_WEIGHT          # tolérance aux variations d'éclairage
        dist = np.sqrt((diff ** 2).sum(axis=2))
        mask = ((dist < config.SKIN_COLOR_TOLERANCE) & (zone > 0)).astype(np.uint8) * 255
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        return FaceRegionExtractor._fill_holes(mask, config.SKIN_HOLE_MAX_PX)

    @staticmethod
    def _fill_holes(mask, max_area):
        """Rebouche les trous ENTOURÉS de peau (boutons rouges, taches, ombres) : ils font partie
        de la peau à analyser. Les cheveux et le fond touchent le bord et ne sont pas des trous."""
        inv = (mask == 0).astype(np.uint8)
        n, lab, stats, _ = cv2.connectedComponentsWithStats(inv, connectivity=4)
        h, w = mask.shape
        out = mask.copy()
        for i in range(1, n):
            x, y, bw, bh, area = stats[i]
            touches_border = x == 0 or y == 0 or x + bw >= w or y + bh >= h
            if not touches_border and area <= max_area:
                out[lab == i] = 255
        return out

    def _build_masks(self, img, pts):
        shape = img.shape[:2]
        masks = {name: self._fill(shape, pts[idx], convex, shrink)
                 for name, (idx, convex, shrink) in self.layout["zones"].items()}
        if "front" not in masks:
            masks["front"] = self._forehead_from_brows(shape, pts)
        masks["patte_oie_g"] = self._crow_feet(shape, pts, *self.layout["eye_g"])
        masks["patte_oie_d"] = self._crow_feet(shape, pts, *self.layout["eye_d"])

        # On retire yeux, sourcils et lèvres (élargis) de toutes les zones
        exclusion = np.zeros(shape, np.uint8)
        for idx in self.layout["exclude"]:
            exclusion |= self._fill(shape, pts[idx], convex=True)
        r = max(3, int(config.NORM_EYE_DIST * 0.03))
        exclusion_raw = exclusion.copy()
        exclusion = cv2.dilate(exclusion, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1,) * 2))

        # Masque de tout le visage (enveloppe des points + front), sans yeux/sourcils/lèvres
        face = self._fill(shape, pts, convex=True) | masks["front"]
        face_mask = face & ~exclusion_raw

        erode = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        for name in masks:
            masks[name] = cv2.erode(masks[name] & ~exclusion, erode)

        # Ne garder que les pixels couleur peau, zone par zone
        lab = cv2.cvtColor(cv2.GaussianBlur(img, (0, 0), 2), cv2.COLOR_BGR2LAB).astype(np.float32)
        for name in masks:
            masks[name] = cv2.erode(self._skin_color_mask(lab, masks[name]), erode)
        return masks, face_mask
