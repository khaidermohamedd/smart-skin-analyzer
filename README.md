# Smart Skin Analyzer : miroir intelligent IoT + IA

Miroir intelligent qui analyse la peau du visage (**acné, rides, taches, pores**) avec une caméra
et des modèles d'apprentissage profond, complété par des capteurs sans contact (température de la
peau, distance, température et humidité de l'air). Projet de Master IoT.

- **Pour reprendre le travail** : [`docs/CONTEXTE_SESSION.md`](docs/CONTEXTE_SESSION.md)
- **Guide complet** (réalisation, explication des scripts, résultats, câblage) :
  [`docs/Guide_Realisation_Skin_Analyzer.pdf`](docs/Guide_Realisation_Skin_Analyzer.pdf)

## Structure

| Dossier | Contenu |
|---|---|
| `skin_analyzer/` | Analyse du visage : zones, détecteurs classiques, modèles profonds (ONNX), scores |
| `mirror/` | Application du miroir (Raspberry Pi) : capteurs, caméra, écrans, historique |
| `firmware/` | Programme de l'ESP32 (Arduino) : MLX90614, VL53L0X/L1X, DHT22, LED RGB |
| `deploy/` | Installation du Raspberry Pi et démarrage automatique |
| `training/` | Téléchargement des bases, préparation, entraînement (YOLO11, U-Net), suivi |
| `tools/`, `tests/` | Test de l'ESP32, test par injection de défauts |
| `docs/` | Guide PDF, générateur du guide, résultats d'entraînement |

## Démarrage rapide

```bash
git clone https://github.com/khaidermohamedd/smart-skin-analyzer.git
cd smart-skin-analyzer
git lfs pull                      # modèles (≈ 250 Mo)
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m skin_analyzer.main --image samples/astronaut.png --no-show
python -m mirror.app --sim --image samples/astronaut.png --windowed   # miroir sans matériel
```

Sur le Raspberry Pi : `bash deploy/setup_pi.sh` (voir le chapitre 9 du guide).

## Modèles et données

| Modèle | Base | Score sur le test |
|---|---|---|
| YOLO11s (acné) | ACNE04 (Wu et al., ICCV 2019, usage académique) | mAP@50 = 0,34 |
| U-Net ResNet-50 (rides) | FFHQ-Wrinkle (Moon et al., ICPR 2024, CC BY-NC-SA 4.0) | IoU = 0,47, F1 = 0,64 |

Les bases ne sont pas dans le dépôt : `python -m training.download_data` les télécharge.

**Indication cosmétique, pas un diagnostic médical.**
