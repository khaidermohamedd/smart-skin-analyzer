"""ACNE04 (annotations VOC) -> jeu YOLO découpé en tuiles.

Pourquoi des tuiles : les boutons font ~0,5-2 % de la largeur d'une photo ACNE04.
Réduire la photo entière à 1024 px les ferait presque disparaître. On garde donc la
résolution d'origine et on découpe des tuiles de TILE px qui se chevauchent.
On ajoute aussi l'image entière réduite (contexte global du visage).

Le découpage train/val/test se fait PAR PHOTO (jamais deux tuiles d'une même
photo dans deux ensembles différents), sinon l'évaluation serait trop optimiste.

    python -m training.prepare_acne_data
"""
import random
import shutil
import xml.etree.ElementTree as ET
from collections import Counter

import cv2
import numpy as np

from .paths import DATA

SRC = DATA / "acne04"
OUT = DATA / "acne_yolo"
TILE = 1024
OVERLAP = 0.25
MIN_VISIBLE = 0.5        # fraction de la boîte qui doit être dans la tuile
SPLITS = (0.8, 0.1, 0.1)
SEED = 42


def read_voc(xml_path):
    root = ET.parse(xml_path).getroot()
    boxes = []
    for obj in root.iter("object"):
        bb = obj.find("bndbox")
        boxes.append([float(bb.findtext(k)) for k in ("xmin", "ymin", "xmax", "ymax")])
    return root.findtext("filename"), np.array(boxes, np.float32).reshape(-1, 4)


def tile_starts(length, tile, overlap):
    if length <= tile:
        return [0]
    step = int(tile * (1 - overlap))
    starts = list(range(0, length - tile, step)) + [length - tile]
    return sorted(set(starts))


def yolo_lines(boxes, x0, y0, w, h):
    lines = []
    for bx0, by0, bx1, by1 in boxes:
        cx0, cy0 = max(bx0, x0), max(by0, y0)
        cx1, cy1 = min(bx1, x0 + w), min(by1, y0 + h)
        if cx1 <= cx0 or cy1 <= cy0:
            continue
        visible = (cx1 - cx0) * (cy1 - cy0) / max((bx1 - bx0) * (by1 - by0), 1e-6)
        if visible < MIN_VISIBLE:
            continue
        lines.append(f"0 {((cx0 + cx1) / 2 - x0) / w:.6f} {((cy0 + cy1) / 2 - y0) / h:.6f} "
                     f"{(cx1 - cx0) / w:.6f} {(cy1 - cy0) / h:.6f}")
    return lines


def write(split, name, img, lines, stats):
    cv2.imwrite(str(OUT / split / "images" / f"{name}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    (OUT / split / "labels" / f"{name}.txt").write_text("\n".join(lines) + ("\n" if lines else ""))
    stats[split]["images"] += 1
    stats[split]["boites"] += len(lines)


def main():
    xmls = sorted(SRC.rglob("*.xml"))
    if not xmls:
        raise SystemExit(f"Aucune annotation XML dans {SRC} : lancez d'abord training.download_data acne")
    images = {p.name: p for p in SRC.rglob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png")}

    if OUT.exists():
        shutil.rmtree(OUT)
    for s in ("train", "val", "test"):
        (OUT / s / "images").mkdir(parents=True)
        (OUT / s / "labels").mkdir(parents=True)

    random.seed(SEED)
    random.shuffle(xmls)
    n = len(xmls)
    stats = {s: Counter() for s in ("train", "val", "test")}
    sizes = Counter()
    for i, xml in enumerate(xmls):
        split = "train" if i < SPLITS[0] * n else ("val" if i < (SPLITS[0] + SPLITS[1]) * n else "test")
        fname, boxes = read_voc(xml)
        path = images.get(fname) or images.get(f"{xml.stem}.jpg")
        if path is None:
            continue
        img = cv2.imread(str(path))
        H, W = img.shape[:2]
        sizes[(W, H)] += 1
        stats[split]["photos"] += 1
        stats[split]["lesions"] += len(boxes)

        # 1) tuiles en pleine résolution
        for y0 in tile_starts(H, TILE, OVERLAP):
            for x0 in tile_starts(W, TILE, OVERLAP):
                tw, th = min(TILE, W), min(TILE, H)
                lines = yolo_lines(boxes, x0, y0, tw, th)
                # On garde quelques tuiles sans bouton (exemples négatifs), pas toutes
                if not lines and random.random() > 0.3:
                    continue
                write(split, f"{xml.stem}_{x0}_{y0}", img[y0:y0 + th, x0:x0 + tw], lines, stats)

        # 2) photo entière réduite
        s = TILE / max(H, W)
        small = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        write(split, f"{xml.stem}_full", small, yolo_lines(boxes * s, 0, 0, small.shape[1], small.shape[0]), stats)

    (OUT / "data.yaml").write_text(
        f"path: {OUT.as_posix()}\ntrain: train/images\nval: val/images\ntest: test/images\n"
        f"names: ['acne']\n")
    print("Tailles des photos :", sizes.most_common(3))
    for s, c in stats.items():
        print(f"{s:5s} photos={c['photos']:4d} lésions={c['lesions']:5d} -> "
              f"tuiles={c['images']:5d} boîtes={c['boites']:6d}")
    print(f"-> {OUT / 'data.yaml'}")


if __name__ == "__main__":
    main()
