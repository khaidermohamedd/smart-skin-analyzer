"""Affiche l'avancement des entraînements (à lancer depuis Windows, n'importe quel Python).

    python -m training.status        ou double-clic sur status.bat
"""
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

RUNS = Path(os.environ.get("SKIN_AI_RUNS", "D:/skin_ai/runs"))
ACTIVE_SECONDS = 15 * 60       # sans écriture depuis 15 min => probablement arrêté


def hms(sec):
    sec = int(sec)
    return f"{sec // 3600} h {sec % 3600 // 60:02d} min"


def state(path, done):
    if done:
        return "TERMINÉ ✔"
    if path is None or not path.exists():
        return "pas encore démarré"
    age = time.time() - path.stat().st_mtime
    return "EN COURS" if age < ACTIVE_SECONDS else f"ARRÊTÉ ? (aucune mise à jour depuis {hms(age)})"


def acne():
    print("━━━ ACNÉ (YOLO11 sur ACNE04) ━━━")
    dirs = [d for d in (RUNS / "acne").iterdir() if d.is_dir() and not d.name.startswith("essai")
            and not d.name.endswith("_test")] if (RUNS / "acne").exists() else []
    if not dirs:
        print("  État : pas encore démarré\n")
        return
    run = max(dirs, key=lambda d: d.stat().st_mtime)
    res = run / "results.csv"
    if not res.exists():
        log = RUNS / "acne_train.log"
        print(f"  Dossier : {run}")
        print(f"  État    : {state(log, False)} (première epoch en cours, ≈ 6 min)\n")
        return
    done_file = run / "test_metrics.json"
    rows = list(csv.DictReader(open(res, encoding="utf-8")))
    rows = [{k.strip(): v for k, v in r.items()} for r in rows]
    total = None
    args = run / "args.yaml"
    if args.exists():
        for line in args.read_text().splitlines():
            if line.startswith("epochs:"):
                total = int(line.split(":")[1])
    print(f"  Dossier : {run}")
    print(f"  État    : {state(res, done_file.exists())}")
    if rows:
        last = rows[-1]
        ep = int(float(last["epoch"]))
        print(f"  Epoch   : {ep} / {total or '?'}")
        if "time" in last and total and not done_file.exists():
            per = float(last["time"]) / max(ep, 1)
            print(f"  Durée   : {hms(float(last['time']))} écoulées, ≈ {hms(per * (total - ep))} restantes "
                  f"(max ; l'arrêt automatique peut finir plus tôt)")
        best = max(rows, key=lambda r: float(r.get("metrics/mAP50(B)", 0)))
        print(f"  Validation (dernière epoch) : précision={float(last['metrics/precision(B)']):.3f} "
              f"rappel={float(last['metrics/recall(B)']):.3f} mAP50={float(last['metrics/mAP50(B)']):.3f}")
        print(f"  Meilleur mAP50 validation   : {float(best['metrics/mAP50(B)']):.3f} "
              f"(epoch {int(float(best['epoch']))})")
    if done_file.exists():
        print("  ► SCORES SUR LE TEST :", json.loads(done_file.read_text()))
    print()


def wrinkles():
    print("━━━ RIDES (U-Net sur FFHQ-Wrinkle) ━━━")
    base = RUNS / "wrinkles"
    prog = base / "progress.json"
    done_file = base / "test_metrics.json"
    print(f"  État    : {state(prog, done_file.exists())}")
    if prog.exists():
        p = json.loads(prog.read_text())
        etape = "1/2 pré-entraînement" if p["etape"] == "pretrain" else "2/2 ajustement fin"
        print(f"  Étape   : {etape}")
        print(f"  Epoch   : {p['epoch']} / {p['epochs']}   ({p['secondes_par_epoch']} s par epoch)")
        if not done_file.exists():
            rest = (p["epochs"] - p["epoch"]) * p["secondes_par_epoch"]
            print(f"  Restant : ≈ {hms(rest)} pour cette étape")
        print(f"  Meilleur IoU validation : {p['meilleur_val_IoU']}   (mis à jour : {p['maj']})")
    if done_file.exists():
        print("  ► SCORES SUR LE TEST :", json.loads(done_file.read_text()))
    print()


def gpu():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,temperature.gpu",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10)
        u, m, t = [x.strip() for x in out.stdout.strip().split(",")]
        print(f"Carte graphique : utilisation {u} %, mémoire {m} Mo, {t} °C")
    except Exception:
        pass


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(time.strftime("%d/%m/%Y %H:%M:%S"), "\n")
    acne()
    wrinkles()
    gpu()
    print("Journaux détaillés : D:\\skin_ai\\runs\\acne_train.log et wrinkles_train.log")
