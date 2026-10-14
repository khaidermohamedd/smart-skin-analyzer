"""Lancement en ligne de commande.

    python -m skin_analyzer.main --image photo.jpg
    python -m skin_analyzer.main --camera 0
        ESPACE = analyser   Z = afficher/masquer les zones   Q = quitter
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import cv2

from .analyzer import SkinAnalyzer, report_to_json
from .visualize import annotate, draw_landmarks

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def save(report, annotated, stem=None):
    RESULTS_DIR.mkdir(exist_ok=True)
    stem = stem or datetime.now().strftime("%Y%m%d_%H%M%S")
    cv2.imwrite(str(RESULTS_DIR / f"{stem}_analyse.jpg"), annotated)
    with open(RESULTS_DIR / f"{stem}_rapport.json", "w", encoding="utf-8") as f:
        json.dump(report_to_json(report), f, ensure_ascii=False, indent=2)
    return RESULTS_DIR / f"{stem}_analyse.jpg"


def print_report(report):
    q = report["qualite"]
    print(f"\n=== Score peau : {report['score_peau']}/100  ({report['duree_ms']} ms) ===")
    for name, r in report["criteres"].items():
        print(f"  {name:7s} score={r['score']:5.1f}  {r['niveau']:7s} "
              f"{r['mesure']} {r['unite']}  par zone={r['par_zone']}")
    for w in q["avertissements"]:
        print("  ! " + w)


def fit(img, max_h=900):
    s = min(1.0, max_h / img.shape[0])
    return cv2.resize(img, None, fx=s, fy=s) if s < 1 else img


def run_image(analyzer, path, show):
    bgr = cv2.imread(str(path))
    if bgr is None:
        raise SystemExit(f"Impossible de lire l'image : {path}")
    report, regions = analyzer.analyze(bgr)
    if report is None:
        raise SystemExit("Aucun visage détecté.")
    print_report(report)
    out = save(report, annotate(report, regions), Path(path).stem)
    print(f"Résultat enregistré : {out}")
    if show:
        cv2.imshow("Analyse de peau", fit(cv2.imread(str(out))))
        cv2.waitKey(0)


def run_camera(analyzer, index, width, height):
    cap = cv2.VideoCapture(index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    if not cap.isOpened():
        raise SystemExit(f"Caméra {index} introuvable.")
    show_zones = True
    print("ESPACE = analyser | Z = zones | Q = quitter")
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)                      # effet miroir
        preview = frame.copy()
        pts = analyzer.extractor.detect_landmarks(frame)
        if pts is not None:
            preview = draw_landmarks(preview, pts, step=6)
        else:
            cv2.putText(preview, "Aucun visage", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.imshow("Miroir - apercu", fit(preview, 720))

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("z"):
            show_zones = not show_zones
        if key == ord(" "):
            report, regions = analyzer.analyze(frame)
            if report is None:
                print("Aucun visage détecté.")
                continue
            print_report(report)
            annotated = annotate(report, regions, show_zones)
            print(f"Résultat enregistré : {save(report, annotated)}")
            cv2.imshow("Analyse de peau", fit(annotated))
    cap.release()
    cv2.destroyAllWindows()


def main():
    sys.stdout.reconfigure(encoding="utf-8")    # accents dans la console Windows
    p = argparse.ArgumentParser(description="Analyse de peau : acné, rides, taches, pores")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--image", help="chemin d'une photo du visage")
    src.add_argument("--camera", type=int, help="index de la webcam (0, 1, ...)")
    p.add_argument("--width", type=int, default=1920)
    p.add_argument("--height", type=int, default=1080)
    p.add_argument("--backend", choices=["auto", "mediapipe", "opencv"], default="auto",
                   help="moteur de points du visage")
    p.add_argument("--no-show", action="store_true", help="ne pas ouvrir de fenêtre")
    args = p.parse_args()

    analyzer = SkinAnalyzer(args.backend)
    try:
        if args.image:
            run_image(analyzer, args.image, not args.no_show)
        else:
            run_camera(analyzer, args.camera, args.width, args.height)
    finally:
        analyzer.close()


if __name__ == "__main__":
    main()
