"""Télécharge les deux bases d'entraînement.

  * FFHQ-Wrinkle (rides) : 1 000 masques annotés à la main + 50 000 masques "faibles"
    générés automatiquement (Moon et al., ICPR 2024, CC BY-NC-SA 4.0), et les photos
    FFHQ correspondantes (miroir Hugging Face). Les masques faibles servent au
    pré-entraînement (méthode de l'article) : on en prend N_WEAK.
  * ACNE04 (acné) : 1 457 visages, 18 983 lésions en boîtes (Wu et al., ICCV 2019,
    usage académique).

    python -m training.download_data            # les deux
    python -m training.download_data wrinkles   # une seule

Les données vont dans %SKIN_AI_DIR%/datasets (par défaut D:/skin_ai/datasets),
hors du dossier OneDrive.
"""
import os
import sys
import tarfile
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SKIN_AI_DIR = Path(os.environ.get("SKIN_AI_DIR", "D:/skin_ai"))
DATA = SKIN_AI_DIR / "datasets"
N_WEAK = int(os.environ.get("N_WEAK", 10000))   # images pour le pré-entraînement

WRINKLE_MASKS_GDRIVE = "https://drive.google.com/uc?id=1vzbx847hq1hgKjMtMmxLzmzLrYb4t0QX"
WEAK_MASKS_GDRIVE = "https://drive.google.com/uc?id=1dLl7_ChsJNrZSQIbNGj21sm45hmH0ZxC"
FFHQ_URL = "https://huggingface.co/datasets/marcosv/ffhq-dataset/resolve/main/Part{part}/{id}.png"
ACNE04_GDRIVE_FOLDER = "https://drive.google.com/drive/folders/18yJcHXhzOv7H89t-Lda6phheAicLqMuZ"


def _fetch(url, dst, retries=4):
    if dst.exists() and dst.stat().st_size > 0:
        return True
    tmp = dst.with_suffix(".part")
    for _ in range(retries):
        try:
            urllib.request.urlretrieve(url, tmp)
            tmp.replace(dst)
            return True
        except Exception:
            continue
    return False


def _download_zip(url, base, folder):
    import gdown
    if (base / folder).exists():
        return
    base.mkdir(parents=True, exist_ok=True)
    z = base / f"{folder}.zip"
    if not z.exists():
        gdown.download(url, str(z), quiet=False)
    zipfile.ZipFile(z).extractall(base)
    z.unlink()


def _download_images(ids, images):
    images.mkdir(parents=True, exist_ok=True)
    jobs = [(FFHQ_URL.format(part=int(i) // 10000 + 1, id=i), images / f"{i}.png") for i in ids]
    done = 0
    with ThreadPoolExecutor(8) as pool:
        for ok in pool.map(lambda j: _fetch(*j), jobs):
            done += ok
            if done % 250 == 0:
                print(f"  FFHQ : {done}/{len(jobs)}", flush=True)
    return done, len(jobs)


def wrinkles():
    base = DATA / "ffhq_wrinkle"
    _download_zip(WRINKLE_MASKS_GDRIVE, base, "manual_wrinkle_masks")
    manual = sorted(p.stem for p in (base / "manual_wrinkle_masks").glob("*.png"))
    done, n = _download_images(manual, base / "images")
    print(f"FFHQ-Wrinkle manuel : {done}/{n} images")

    if N_WEAK > 0:
        _download_zip(WEAK_MASKS_GDRIVE, base, "weak_wrinkle_masks")
        weak_dir = next(p for p in base.iterdir() if p.is_dir() and p.name.startswith("weak"))
        manual_set = set(manual)
        weak = sorted(p.stem for p in weak_dir.rglob("*.png") if p.stem not in manual_set)[:N_WEAK]
        done, n = _download_images(weak, base / "images")
        print(f"FFHQ-Wrinkle faible : {done}/{n} images")


def acne04():
    import gdown  # noqa: F401
    base = DATA / "acne04"
    base.mkdir(parents=True, exist_ok=True)
    gdown.download_folder(ACNE04_GDRIVE_FOLDER, output=str(base), quiet=False)
    for arc in list(base.rglob("*.tar")) + list(base.rglob("*.tar.gz")) + list(base.rglob("*.zip")):
        print("  extraction", arc.name)
        if arc.suffix == ".zip":
            zipfile.ZipFile(arc).extractall(arc.parent)
        else:
            with tarfile.open(arc) as t:
                t.extractall(arc.parent)
    print(f"ACNE04 -> {base}")


if __name__ == "__main__":
    which = sys.argv[1:] or ["wrinkles", "acne"]
    if "wrinkles" in which:
        wrinkles()
    if "acne" in which:
        acne04()
