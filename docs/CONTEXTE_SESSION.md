# Contexte du projet : où on en est (à lire pour reprendre)

> Ce fichier résume tout le travail fait avec Claude Code (sessions du 5 au 14 octobre 2026),
> pour pouvoir **reprendre sur un autre appareil**. Pour continuer avec Claude Code :
> cloner le dépôt, l'ouvrir, et dire : *« Lis docs/CONTEXTE_SESSION.md et continuons. »*
>
> Le guide complet (24 pages, schémas, scores, explications de chaque script) est dans
> [`docs/Guide_Realisation_Skin_Analyzer.pdf`](Guide_Realisation_Skin_Analyzer.pdf).

## 1. Le projet

**Smart Skin Analyzer** : miroir intelligent IoT + IA (projet de Master). Une caméra analyse le
visage et mesure 4 critères (**acné, rides, taches, pores**), des capteurs sans contact ajoutent
température de la peau, température et humidité de l'air ; le miroir affiche un score, des
conseils (non médicaux) et garde un historique.

**Matériel** : Raspberry Pi 4 Model B, Pi Camera Module 3, écran HDMI 5" (800×480), miroir sans
tain (ou film), ESP32 (relié au Pi par câble USB-A → USB-C), MLX90614 (température IR),
VL53L0X/VL53L1X (distance), DHT22 (air), LED RGB simple.

## 2. Ce qui est fait

| Partie | Dossier | État |
|---|---|---|
| Analyse classique (zones du visage, taches, pores) | `skin_analyzer/` | Fait, testé |
| Modèle **acné** YOLO11s sur ACNE04 | `skin_analyzer/models/acne_yolo.onnx` | Entraîné, intégré |
| Modèle **rides** U-Net (ResNet-50) sur FFHQ-Wrinkle | `skin_analyzer/models/wrinkle_unet.onnx` | Entraîné, intégré |
| Scripts d'entraînement (téléchargement, préparation, entraînement, suivi) | `training/` | Fait |
| Firmware ESP32 (3 capteurs + LED, JSON par USB) | `firmware/esp32_capteurs/` | **Compile** (pas encore testé sur la carte) |
| Programme du miroir (machine à états, écrans, historique) | `mirror/` | **Testé en simulation** |
| Installation du Pi + démarrage auto | `deploy/` | Écrit, pas encore testé |
| Guide PDF (généré par `docs/build_guide.py`) | `docs/` | À jour |

### Résultats mesurés (images jamais vues pendant l'entraînement)

- **Acné (ACNE04, 145 photos de test)** : précision 0,44, rappel 0,40, **mAP@50 = 0,34**,
  mAP@50-95 = 0,09. Seuil de confiance retenu : **0,16** (F1 max sur la validation).
  Dans l'application, par photo (125 photos) : **corrélation 0,75** entre boutons détectés et
  annotés, mais le modèle en trouve ~la moitié (6,1 contre 11,5).
  → Résultat moyen, en dessous de l'objectif (0,4-0,6). Piste « version 2 » proposée, non lancée.
- **Rides (FFHQ-Wrinkle, 100 visages de test)** : **IoU 0,47, F1 0,64**, précision 0,63,
  rappel 0,66, seuil 0,55. Bon résultat. Le pré-entraînement sur masques faibles n'a rien apporté
  de visible ; c'est l'ajustement fin sur les 1 000 masques manuels qui compte.
- Étalonnage des scores (dans `skin_analyzer/config.py`) : rides 2,1 mm/cm² (médiane FFHQ → 35/100),
  acné 3,5 boutons détectés.
- Détails : `docs/resultats/` (courbes, logs, métriques, découpage du test).

### Décisions importantes (et pourquoi)

- **Deux modèles profonds seulement** (acné, rides), sur demande. Taches et pores restent en
  vision classique : pas de base publique fiable (Roboflow « Skin-Problem-Detection » écartée :
  images 255×255, annotations incohérentes).
- **YOLO11s au lieu de YOLO11m** : YOLO11m en 1024 px ne tient qu'en lots de 2 sur la RTX 2070
  (≈ 65 h d'entraînement). Priorité à la résolution (petits boutons).
- **Acné : tuiles de 1024 px** à la résolution d'origine ; découpage train/val/test **par photo**.
  À l'utilisation, le visage est remis à l'échelle d'ACNE04 (**860 px entre les coins des yeux**).
- **Rides : alignement FFHQ** reproduit à l'utilisation (même cadrage qu'à l'entraînement).
- **Masque couleur de peau** : les trous entourés de peau sont rebouchés (sinon les boutons rouges
  étaient exclus de l'analyse - bug corrigé).
- Modèles exportés en **ONNX, lus par OpenCV DNN** (pas de PyTorch sur le Pi).

## 3. Environnement sur le PC d'origine (Windows)

- **Smart App Control** (Windows 11) bloque les DLL de MediaPipe, PyTorch et scikit-image.
  → Le code tourne sous **WSL2 Ubuntu 24.04** nommé `skinai`, installé dans `D:\skin_ai\wsl`.
  Environnement Python : `/opt/skinai/venv` (PyTorch CUDA 12.6, Ultralytics, OpenCV contrib…).
  Installation : `training/wsl_setup.sh`. Entraînements : `training/wsl_train.sh acne|wrinkles`.
- Disque C: presque plein → tout est sur **D:\skin_ai** (`code`, `datasets` ≈ 25 Go, `runs`, `wsl`).
- **Pas dans le dépôt** : `datasets/` (re-téléchargeables avec `python -m training.download_data`),
  `runs/` (sauf l'essentiel copié dans `docs/resultats/`), la clé Roboflow (inutile désormais).
- GPU : NVIDIA RTX 2070 (8 Go).

## 4. Étape en cours : configuration du Raspberry Pi

L'utilisateur a reçu le Raspberry Pi 4 Model B. Instructions données (étape 1 en cours) :

1. **Raspberry Pi Imager** → Raspberry Pi 4, *Raspberry Pi OS (64-bit)* avec bureau, carte microSD.
   Réglages : nom d'hôte **`skinmirror`**, utilisateur au choix, Wi-Fi (pays **MA**),
   fuseau `Africa/Casablanca`, clavier `fr`, **SSH par clé publique** avec la clé du PC d'origine :
   `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIxmNvzpltkb2NmRM1NOEqE6IBS5MHa6ENrCZkpQ45BD pc-moham-skinmirror`
   (la clé privée correspondante est **seulement** sur le PC d'origine, `C:\Users\moham\.ssh\id_ed25519`).
   Depuis un autre appareil, il faudra y ajouter sa propre clé publique, ou utiliser un mot de passe.
2. Branchements (Pi éteint) : nappe caméra dans **CAMERA** (contacts vers les prises HDMI),
   écran sur **micro-HDMI 0**, microSD dessous, ESP32 en USB, alimentation 5 V / 3 A en dernier.
3. Ensuite (prévu) : se connecter en SSH (`ssh <utilisateur>@skinmirror.local`), copier le projet
   (`git clone` de ce dépôt + `git lfs pull`), lancer `bash deploy/setup_pi.sh`, tester la caméra
   (`rpicam-still -o test.jpg`), l'ESP32 (`python tools/test_esp32.py`), **mesurer le temps
   d'analyse sur le Pi** (si trop lent : `WRINKLE_TTA = False` dans `skin_analyzer/config.py`).

En attente de l'utilisateur : nom d'utilisateur choisi, et confirmation que le bureau s'affiche.

## 4 bis. Partie capteurs du binôme (intégrée le 18/10/2026)

Dépôt de J. Salek : https://github.com/jihanesalek263-png/SmartSkinAnalyzer (copie locale : `D:\skin_ai\externe\`).
Arduino **Uno** + MLX90614 + DHT22 + **Sharp IR analogique** (A0), JSON toutes les 2 s :
`{"distance_cm":..,"temp_peau":..,"temp_air":..,"humidite":..}` ; règles fixes → type de peau
(sèche / normale / mixte / grasse).

- `mirror/esp32.py` accepte **les deux cartes** (ESP32 de ce dépôt et Uno du binôme), format détecté seul.
- `mirror/skin_type.py` reprend ses règles à l'identique (vérifié : 200/200 sur son dataset) ;
  affiché « indicatif » sur l'écran de résultats, conseil adapté si la mesure est fiable.
- **Limites signalées** : ce sont des règles, pas un modèle entraîné (son dataset est généré par ces
  mêmes règles) ; le DHT22 mesure l'humidité de l'**air**, pas l'hydratation de la peau ; le MLX90614
  n'est fiable qu'entre 10 et 30 cm alors que la photo se prend à 30-48 cm.
- **Décidé (18/10)** : carte finale = **Arduino Uno + Sharp IR**. Firmware adapté :
  `firmware/uno_capteurs/uno_capteurs.ino` (même JSON que le binôme, envoi 4×/s, LED RGB sur D9/D10/D11,
  compile : 40 % flash / 34 % RAM). L'ESP32 reste une variante compatible.
- **Décidé (18/10)** : température en **2 temps** : photo à 30-48 cm, puis « Approchez-vous à 20 cm »,
  4 lectures dans 10-30 cm, médiane ; l'analyse IA tourne en parallèle (état `temperature` dans `app.py`).
- Option non retenue pour l'instant : capteur capacitif d'hydratation au contact.

## 4 ter. État du Raspberry Pi (18/10/2026)

- Pi 4 Model B 4 Go, Raspberry Pi OS 13 (Trixie) 64 bits, Python 3.13, `pi@skinmirror` = **192.168.1.31**.
  Accès SSH par la clé du PC d'origine (ajoutée dans `~/.ssh/authorized_keys`).
- Projet dans `/home/pi/skin_ai` (copie, pas un dépôt Git). Des modifications faites directement sur le Pi
  le 15/10 (rafale photo + mise au point sur le visage, aperçu caméra en direct, clavier evdev, extinction par
  Échap maintenu, onnxruntime, MediaPipe retiré car il plante sur le Pi 4) ont été récupérées dans la branche
  `pi-modifs` puis **fusionnées** dans `main` (commit 67a3187) et réinstallées sur le Pi. Sauvegarde de
  l'ancienne version : `~/skin_ai_sauvegarde_avant_maj_20261018.tgz` sur le Pi.
- Test complet sur le Pi (photo de test, capteurs simulés) : OK, type de peau OK.
- **Temps d'analyse sur le Pi 4 : 114 s** (acné 44 s, rides 70 s avec 2 passages / 40 s avec 1, chargement
  des modèles 10 s une seule fois). À optimiser.
- **Caméra non détectée** depuis le redémarrage du 18/10 (elle fonctionnait le 15/10 : 4 analyses dans
  `~/skin_history`). Le miroir affiche maintenant « Caméra non détectée » et réessaie au lieu de planter.
- Arduino Uno pas encore branché sur le Pi.
- **Pas de capteur de distance (Sharp) pour l'instant** : `HAS_DISTANCE_SENSOR = False` dans `mirror/config.py`.
  Analyse lancée par la touche ESPACE ; température lue après la consigne « approchez-vous à 20 cm »
  (4 s pour se placer), en ne gardant que les lectures plausibles 28-38,5 °C ; résultats affichés 30 s.
  Remettre `True` quand le Sharp sera branché (rouge 5V, noir GND, jaune A0).

## 5. Reste à faire

- [ ] Câbler l'ESP32 (figure 8 du guide), téléverser le firmware (LED rouge → vert → bleu au démarrage),
      tester avec `tools/test_esp32.py`.
- [ ] Installer et tester le Pi (section 4 ci-dessus), mesurer le temps d'analyse réel.
- [ ] Montage : capteurs VL53L0X et MLX90614 **hors du verre** (le verre bloque l'IR), petit trou
      dans le film miroir devant la caméra. MLX90614 GY-906 BAA = angle 90° → sous-estime la
      température de la peau à 40 cm.
- [ ] Calibrer les seuils taches/pores sur des photos prises par la caméra du miroir.
- [ ] (Option) Acné version 2 : sans photos réduites, tuiles agrandies (~10-15 h d'entraînement).
- [ ] (Option) MQTT pour un tableau de bord IoT.

## 6. Commandes utiles

```bash
# Analyse d'une photo (Linux / WSL / Pi)
python -m skin_analyzer.main --image photo.jpg --no-show
# Miroir en simulation, sans matériel (P = personne, ESPACE = analyse)
python -m mirror.app --sim --image photo.jpg --windowed
# Test automatique du miroir sans écran
python -m mirror.app --sim --scenario --image photo.jpg --dump /tmp/ecrans
# Régénérer le guide PDF
python docs/build_guide.py
# Compiler le firmware sans carte (Linux)
bash firmware/compile_check.sh
```
