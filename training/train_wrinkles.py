"""Segmentation des rides (U-Net) sur FFHQ-Wrinkle, méthode en 2 étapes de l'article
(Moon et al., ICPR 2024) :
  1. pré-entraînement sur les masques "faibles" (générés automatiquement, beaucoup d'images)
  2. ajustement fin sur les 1 000 masques annotés à la main

    python -m training.train_wrinkles                       # les 2 étapes
    python -m training.train_wrinkles --stage finetune      # étape 2 seule
    python -m training.train_wrinkles --stage test          # évaluation seule

Découpage FIXE des 1 000 masques manuels : 800 train / 100 val / 100 test
(enregistré dans runs/wrinkles/split.json). Le test n'est utilisé qu'à la fin.
Résultats : D:/skin_ai/runs/wrinkles/ ; modèle final -> skin_analyzer/models/wrinkle_unet.onnx
"""
import argparse
import json
import os
import random
import time

from .paths import DATA, MODELS_OUT, RUNS, SKIN_AI_DIR

# Caches des poids pré-entraînés sur D: (pas sur C:)
os.environ.setdefault("HF_HOME", str(SKIN_AI_DIR / "hf_cache"))
os.environ.setdefault("TORCH_HOME", str(SKIN_AI_DIR / "torch_cache"))

import albumentations as A          # noqa: E402
import cv2                          # noqa: E402
import numpy as np                  # noqa: E402
import segmentation_models_pytorch as smp  # noqa: E402
import torch                        # noqa: E402
from torch.utils.data import DataLoader, Dataset  # noqa: E402

BASE = DATA / "ffhq_wrinkle"
OUT = RUNS / "wrinkles"
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)
CROP = 512


# ---------------------------------------------------------------------------
def make_split(seed=42):
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / "split.json"
    if f.exists():
        return json.loads(f.read_text())
    ids = sorted(p.stem for p in (BASE / "manual_wrinkle_masks").glob("*.png")
                 if (BASE / "images" / f"{p.stem}.png").exists())
    random.Random(seed).shuffle(ids)
    split = {"train": sorted(ids[:800]), "val": sorted(ids[800:900]), "test": sorted(ids[900:1000])}
    f.write_text(json.dumps(split))
    return split


def weak_samples(exclude):
    weak_dir = next((p for p in BASE.iterdir() if p.is_dir() and p.name.startswith("weak")), None)
    if weak_dir is None:
        return []
    out = []
    for m in weak_dir.rglob("*.png"):
        img = BASE / "images" / f"{m.stem}.png"
        if m.stem not in exclude and img.exists():
            out.append((img, m))
    return sorted(out)


def train_aug():
    return A.Compose([
        A.HorizontalFlip(p=0.5),
        A.Affine(scale=(0.8, 1.25), rotate=(-12, 12), translate_percent=(-0.05, 0.05), p=0.7),
        A.OneOf([A.CropNonEmptyMaskIfExists(CROP, CROP), A.RandomCrop(CROP, CROP)], p=1.0),
        A.RandomBrightnessContrast(0.25, 0.25, p=0.7),
        A.HueSaturationValue(8, 20, 15, p=0.5),
        A.OneOf([A.GaussNoise(), A.ImageCompression(quality_range=(50, 95)),
                 A.GaussianBlur(blur_limit=(3, 5))], p=0.4),
    ])


class WrinkleDS(Dataset):
    def __init__(self, pairs, aug=None):
        self.pairs, self.aug = pairs, aug

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, i):
        img_p, mask_p = self.pairs[i]
        img = cv2.cvtColor(cv2.imread(str(img_p)), cv2.COLOR_BGR2RGB)
        mask = (cv2.imread(str(mask_p), cv2.IMREAD_GRAYSCALE) > 127).astype(np.uint8)
        if self.aug:
            r = self.aug(image=img, mask=mask)
            img, mask = r["image"], r["mask"]
        x = ((img.astype(np.float32) / 255 - MEAN) / STD).transpose(2, 0, 1)
        return torch.from_numpy(x), torch.from_numpy(mask[None].astype(np.float32))


def manual_pairs(ids):
    return [(BASE / "images" / f"{i}.png", BASE / "manual_wrinkle_masks" / f"{i}.png") for i in ids]


# ---------------------------------------------------------------------------
def build_model(arch, encoder, pretrained=True):
    return getattr(smp, arch)(encoder_name=encoder, encoder_weights="imagenet" if pretrained else None,
                              in_channels=3, classes=1)


class Loss(torch.nn.Module):
    """Dice (chevauchement) + Focal (insiste sur les pixels difficiles) : adapté aux
    structures fines et rares (~0,7 % des pixels sont des rides)."""
    def __init__(self):
        super().__init__()
        self.dice = smp.losses.DiceLoss("binary", from_logits=True)
        self.focal = smp.losses.FocalLoss("binary", alpha=0.75, gamma=2.0)

    def forward(self, logits, y):
        return self.dice(logits, y) + 2.0 * self.focal(logits, y)


@torch.no_grad()
def predict_probs(model, loader, device):
    model.eval()
    probs, gts = [], []
    for x, y in loader:
        with torch.autocast("cuda", enabled=device == "cuda"):
            p = torch.sigmoid(model(x.to(device)).float())
            p = (p + torch.sigmoid(model(torch.flip(x.to(device), [3])).float()).flip([3])) / 2  # TTA miroir
        probs.append(p.cpu())
        gts.append(y)
    return torch.cat(probs), torch.cat(gts)


def metrics(probs, gts, thr):
    pred = probs > thr
    gt = gts > 0.5
    tp = (pred & gt).sum().item()
    fp = (pred & ~gt).sum().item()
    fn = (~pred & gt).sum().item()
    return {
        "IoU(JSI)": tp / max(tp + fp + fn, 1),
        "F1(Dice)": 2 * tp / max(2 * tp + fp + fn, 1),
        "precision": tp / max(tp + fp, 1),
        "rappel": tp / max(tp + fn, 1),
    }


def run_stage(model, train_pairs, val_loader, device, epochs, lr, batch, tag, eval_every):
    loader = DataLoader(WrinkleDS(train_pairs, train_aug()), batch_size=batch, shuffle=True,
                        num_workers=4, pin_memory=True, drop_last=True, persistent_workers=True)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=epochs * len(loader),
                                                pct_start=0.05)
    scaler = torch.amp.GradScaler(enabled=device == "cuda")
    loss_fn = Loss()
    best, best_path, log = -1.0, OUT / f"{tag}_best.pt", []
    for ep in range(1, epochs + 1):
        model.train()
        t0, tot = time.time(), 0.0
        for x, y in loader:
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
            with torch.autocast("cuda", enabled=device == "cuda"):
                loss = loss_fn(model(x), y)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            sched.step()
            tot += loss.item()
        line = f"[{tag}] epoch {ep}/{epochs} loss={tot / len(loader):.4f} ({time.time() - t0:.0f}s)"
        if ep % eval_every == 0 or ep == epochs:
            m = metrics(*predict_probs(model, val_loader, device), 0.5)
            line += f"  val IoU={m['IoU(JSI)']:.4f} F1={m['F1(Dice)']:.4f}"
            log.append({"epoch": ep, **m})
            if m["IoU(JSI)"] > best:
                best = m["IoU(JSI)"]
                torch.save(model.state_dict(), best_path)
                line += "  *meilleur*"
        print(line, flush=True)
        (OUT / f"{tag}_log.json").write_text(json.dumps(log, indent=1))
        (OUT / "progress.json").write_text(json.dumps({
            "etape": tag, "epoch": ep, "epochs": epochs, "loss": round(tot / len(loader), 4),
            "meilleur_val_IoU": round(best, 4), "secondes_par_epoch": round(time.time() - t0),
            "maj": time.strftime("%Y-%m-%d %H:%M:%S")}, indent=1))
    return best_path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--stage", choices=["all", "pretrain", "finetune", "test"], default="all")
    p.add_argument("--arch", default="Unet")
    p.add_argument("--encoder", default="resnet50")
    p.add_argument("--batch", type=int, default=8)
    p.add_argument("--pretrain-epochs", type=int, default=8)
    p.add_argument("--finetune-epochs", type=int, default=120)
    a = p.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Appareil : {device} {torch.cuda.get_device_name(0) if device == 'cuda' else ''}")
    torch.backends.cudnn.benchmark = True
    split = make_split()
    val_loader = DataLoader(WrinkleDS(manual_pairs(split["val"])), batch_size=2, num_workers=2)
    model = build_model(a.arch, a.encoder).to(device)

    if a.stage in ("all", "pretrain"):
        manual = set(sum(split.values(), []))
        weak = weak_samples(manual)
        print(f"Étape 1 - pré-entraînement : {len(weak)} images à masques faibles")
        if weak:
            run_stage(model, weak, val_loader, device, a.pretrain_epochs, 3e-4, a.batch, "pretrain", 1)

    if a.stage in ("all", "finetune"):
        pre = OUT / "pretrain_best.pt"
        if pre.exists():
            model.load_state_dict(torch.load(pre, map_location=device))
            print(f"Départ depuis {pre}")
        print(f"Étape 2 - ajustement fin : {len(split['train'])} images annotées à la main")
        run_stage(model, manual_pairs(split["train"]), val_loader, device,
                  a.finetune_epochs, 1e-4, a.batch, "finetune", 2)

    # --- Évaluation finale -------------------------------------------------
    model.load_state_dict(torch.load(OUT / "finetune_best.pt", map_location=device))
    # Seuil choisi sur la VALIDATION, appliqué tel quel au TEST
    vp, vg = predict_probs(model, val_loader, device)
    thr = max(np.arange(0.2, 0.81, 0.05), key=lambda t: metrics(vp, vg, t)["IoU(JSI)"])
    test_loader = DataLoader(WrinkleDS(manual_pairs(split["test"])), batch_size=2, num_workers=2)
    m = metrics(*predict_probs(model, test_loader, device), thr)
    m = {k: round(v, 4) for k, v in m.items()}
    m["seuil"] = round(float(thr), 2)
    print("\n=== TEST FFHQ-Wrinkle (100 visages jamais vus) ===")
    for k, v in m.items():
        print(f"  {k:10s} {v}")
    (OUT / "test_metrics.json").write_text(json.dumps(m, indent=2))

    # --- Export ONNX pour l'application -----------------------------------
    MODELS_OUT.mkdir(exist_ok=True)
    model.eval().float()
    torch.onnx.export(model, torch.zeros(1, 3, 1024, 1024, device=device),
                      str(MODELS_OUT / "wrinkle_unet.onnx"), input_names=["image"],
                      output_names=["logits"], opset_version=17, dynamo=False)
    (MODELS_OUT / "wrinkle_unet.json").write_text(json.dumps(
        {"arch": a.arch, "encoder": a.encoder, "input": 1024, "seuil": m["seuil"],
         "mean": MEAN.tolist(), "std": STD.tolist(), "test": m}, indent=2))
    print(f"Modèle exporté : {MODELS_OUT / 'wrinkle_unet.onnx'}")


if __name__ == "__main__":
    main()
