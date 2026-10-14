"""Entraînement du détecteur d'acné YOLO11 sur ACNE04 (tuiles 1024 px).

    python -m training.train_acne                 # entraînement complet
    python -m training.train_acne --epochs 3      # essai rapide
    python -m training.train_acne --resume        # reprendre après une coupure

Résultats : D:/skin_ai/runs/acne/<nom>/ (courbes, matrice de confusion, poids)
Le meilleur modèle est copié dans skin_analyzer/models/acne_yolo.pt (+ .onnx).
"""
import argparse
import json
import shutil

from ultralytics import YOLO

from .paths import DATA, MODELS_OUT, RUNS


def data_yaml():
    """data.yaml regénéré avec le chemin du système courant (Windows ou Linux/WSL)."""
    root = DATA / "acne_yolo"
    y = root / "data_local.yaml"
    y.write_text(f"path: {root.as_posix()}\ntrain: train/images\nval: val/images\n"
                 f"test: test/images\nnames: ['acne']\n")
    return y


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="yolo11s.pt", help="yolo11n/s/m/l.pt (s : 1024 px tient dans 8 Go)")
    p.add_argument("--epochs", type=int, default=150)
    p.add_argument("--imgsz", type=int, default=1024)
    p.add_argument("--batch", type=float, default=8, help="images par lot (8 = ~5 Go sur RTX 2070)")
    p.add_argument("--name", default="yolo11s_1024")
    p.add_argument("--resume", action="store_true")
    a = p.parse_args()

    DATA_YAML = data_yaml()
    run_dir = RUNS / "acne" / a.name
    if a.resume:
        model = YOLO(run_dir / "weights" / "last.pt")
        model.train(resume=True)
    else:
        batch = int(a.batch) if a.batch >= 1 else a.batch
        model = YOLO(a.model)
        model.train(
            data=str(DATA_YAML), epochs=a.epochs, imgsz=a.imgsz, batch=batch,
            project=str(RUNS / "acne"), name=a.name, exist_ok=True,
            patience=40,               # arrêt si plus de progrès pendant 40 epochs
            optimizer="AdamW", lr0=0.001, cos_lr=True, warmup_epochs=3,
            amp=True, workers=8, seed=0, deterministic=False, plots=True,
            # Augmentations : variations d'éclairage/couleur du miroir, pose du visage
            hsv_h=0.015, hsv_s=0.5, hsv_v=0.4,
            degrees=10, translate=0.1, scale=0.5, fliplr=0.5,
            mosaic=1.0, mixup=0.1, copy_paste=0.0, close_mosaic=15,
        )

    # --- Évaluation sur le TEST (photos jamais vues) avec le meilleur modèle ---
    best = run_dir / "weights" / "best.pt"
    model = YOLO(best)
    m = model.val(data=str(DATA_YAML), split="test", imgsz=a.imgsz, batch=8,
                  project=str(RUNS / "acne"), name=f"{a.name}_test", exist_ok=True)
    scores = {
        "precision": round(float(m.box.mp), 4),
        "rappel": round(float(m.box.mr), 4),
        "mAP50": round(float(m.box.map50), 4),
        "mAP50-95": round(float(m.box.map), 4),
    }
    print("\n=== TEST ACNE04 ===")
    for k, v in scores.items():
        print(f"  {k:9s} {v}")
    (run_dir / "test_metrics.json").write_text(json.dumps(scores, indent=2))

    MODELS_OUT.mkdir(exist_ok=True)
    shutil.copy2(best, MODELS_OUT / "acne_yolo.pt")
    onnx = model.export(format="onnx", imgsz=a.imgsz, simplify=True, dynamic=False)
    shutil.copy2(onnx, MODELS_OUT / "acne_yolo.onnx")
    print(f"Modèles copiés dans {MODELS_OUT}")


if __name__ == "__main__":
    main()
