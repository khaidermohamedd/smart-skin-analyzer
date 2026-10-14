"""Inférence des modèles d'apprentissage profond (fichiers ONNX lus par OpenCV DNN).

  * acne_yolo.onnx     : YOLO11 entraîné sur ACNE04 (détection, 1 classe)
  * wrinkle_unet.onnx  : U-Net entraîné sur FFHQ-Wrinkle (segmentation des rides)

OpenCV DNN évite toute dépendance supplémentaire (PC Windows et Raspberry Pi).
"""
import json

import cv2
import numpy as np

from . import config


# ---------------------------------------------------------------------------
# Alignement FFHQ (même procédure que NVlabs/ffhq-dataset) : le modèle de rides
# voit ainsi des visages cadrés exactement comme pendant l'entraînement.
def ffhq_quad(eye_l, eye_r, mouth_l, mouth_r):
    eye_avg = (eye_l + eye_r) * 0.5
    eye_to_eye = eye_r - eye_l
    mouth_avg = (mouth_l + mouth_r) * 0.5
    eye_to_mouth = mouth_avg - eye_avg
    x = eye_to_eye - np.flipud(eye_to_mouth) * [-1, 1]
    x /= np.hypot(*x)
    x *= max(np.hypot(*eye_to_eye) * 2.0, np.hypot(*eye_to_mouth) * 1.8)
    y = np.flipud(x) * [-1, 1]
    c = eye_avg + eye_to_mouth * 0.1
    return np.stack([c - x - y, c - x + y, c + x + y, c + x - y]).astype(np.float32)


def align_ffhq(img, quad, size):
    """Retourne (visage aligné size×size, matrice affine image->aligné)."""
    src = quad[[0, 1, 3]]                                   # haut-gauche, bas-gauche, haut-droit
    dst = np.float32([[0, 0], [0, size], [size, 0]])
    M = cv2.getAffineTransform(src, dst)
    aligned = cv2.warpAffine(img, M, (size, size), flags=cv2.INTER_AREA if
                             np.hypot(*(quad[3] - quad[0])) > size else cv2.INTER_CUBIC,
                             borderMode=cv2.BORDER_REFLECT)
    return aligned, M


class WrinkleSegmenter:
    def __init__(self, onnx_path=config.WRINKLE_MODEL, meta_path=config.WRINKLE_META):
        self.net = cv2.dnn.readNetFromONNX(str(onnx_path))
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        self.size = meta.get("input", 1024)
        self.thr = meta.get("seuil", 0.5)
        self.mean = np.array(meta.get("mean", [0.485, 0.456, 0.406]), np.float32)
        self.std = np.array(meta.get("std", [0.229, 0.224, 0.225]), np.float32)
        self.test_metrics = meta.get("test", {})

    def predict(self, bgr, quad, tta=True):
        """Masque de rides (uint8 0/255) dans le repère de `bgr`, et carte de probabilité."""
        aligned, M = align_ffhq(bgr, quad, self.size)
        rgb = cv2.cvtColor(aligned, cv2.COLOR_BGR2RGB).astype(np.float32) / 255
        x = ((rgb - self.mean) / self.std).transpose(2, 0, 1)[None]
        self.net.setInput(np.ascontiguousarray(x))
        logits = self.net.forward()[0, 0]
        if tta:   # 2e passage sur l'image miroir (comme à l'évaluation) ; à couper sur le Pi si trop lent
            self.net.setInput(np.ascontiguousarray(x[..., ::-1]))
            logits = (logits + self.net.forward()[0, 0][:, ::-1]) / 2
        prob = 1 / (1 + np.exp(-logits))
        Minv = cv2.invertAffineTransform(M)
        h, w = bgr.shape[:2]
        prob_img = cv2.warpAffine(prob.astype(np.float32), Minv, (w, h), flags=cv2.INTER_LINEAR)
        return ((prob_img > self.thr) * 255).astype(np.uint8), prob_img


# ---------------------------------------------------------------------------
class AcneDetector:
    def __init__(self, onnx_path=config.ACNE_MODEL, imgsz=1024):
        self.net = cv2.dnn.readNetFromONNX(str(onnx_path))
        self.imgsz = imgsz

    def _run(self, tile):
        """YOLO sur une tuile (letterbox) -> boîtes [x0,y0,x1,y1,score] dans la tuile."""
        h, w = tile.shape[:2]
        s = self.imgsz / max(h, w)
        canvas = np.full((self.imgsz, self.imgsz, 3), 114, np.uint8)
        canvas[:int(round(h * s)), :int(round(w * s))] = cv2.resize(tile, (int(round(w * s)), int(round(h * s))))
        blob = cv2.dnn.blobFromImage(canvas, 1 / 255.0, swapRB=True)
        self.net.setInput(blob)
        out = self.net.forward()[0]                      # (5, N) : cx, cy, w, h, score
        out = out.T
        out = out[out[:, 4] > config.ACNE_CONF * 0.5]
        cx, cy, bw, bh = (out[:, i] / s for i in range(4))
        return np.stack([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2, out[:, 4]], 1)

    def detect(self, bgr, mask=None, tile=1024, overlap=0.25):
        H, W = bgr.shape[:2]
        step = int(tile * (1 - overlap))
        xs = sorted(set(list(range(0, max(W - tile, 0), step)) + [max(W - tile, 0)]))
        ys = sorted(set(list(range(0, max(H - tile, 0), step)) + [max(H - tile, 0)]))
        boxes = []
        for y0 in ys:
            for x0 in xs:
                b = self._run(bgr[y0:y0 + tile, x0:x0 + tile])
                b[:, [0, 2]] += x0
                b[:, [1, 3]] += y0
                boxes.append(b)
        boxes = np.concatenate(boxes) if boxes else np.zeros((0, 5), np.float32)
        if len(boxes) == 0:
            return []
        xywh = [[float(b[0]), float(b[1]), float(b[2] - b[0]), float(b[3] - b[1])] for b in boxes]
        keep = cv2.dnn.NMSBoxes(xywh, boxes[:, 4].tolist(), config.ACNE_CONF, 0.45)
        result = []
        for i in np.array(keep).flatten():
            x0, y0, x1, y1, sc = boxes[i]
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            if mask is not None and not mask[int(np.clip(cy, 0, H - 1)), int(np.clip(cx, 0, W - 1))]:
                continue
            result.append({"x0": float(x0), "y0": float(y0), "x1": float(x1), "y1": float(y1),
                           "score": float(sc)})
        return result
