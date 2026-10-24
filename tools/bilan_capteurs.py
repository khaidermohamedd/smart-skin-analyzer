import json, statistics as st, sys, time
sys.path.insert(0, "/home/pi/skin_ai")
import serial
from mirror.esp32 import find_port
port = find_port()
if not port:
    sys.exit("Aucun Arduino branché sur le Pi")
s = serial.Serial(); s.port, s.baudrate, s.timeout = port, 115200, 1; s.open()
t0, rows, errs = time.time(), [], []
while time.time() - t0 < 15:
    l = s.readline().decode("utf-8", "ignore").strip()
    if not l.startswith("{"): continue
    try: d = json.loads(l)
    except ValueError: continue
    if "erreur" in d: errs.append(d["erreur"]); continue
    d["_t"] = time.time() - t0; rows.append(d)
print(f"port {port} | {len(rows)} mesures en 15 s ({len(rows)/13:.1f} par seconde, hors démarrage)")
print("messages d'erreur :", errs or "aucun")
for k, nom in (("temp_peau", "MLX90614 peau °C"), ("distance_cm", "distance cm"), ("temp_air", "DHT22 air °C"), ("humidite", "DHT22 humidité %")):
    v = [r[k] for r in rows if r.get(k) is not None]
    nul = sum(1 for r in rows if r.get(k) is None)
    if v: print(f"{nom:18s}: {len(v)} valeurs, {nul} vides | min {min(v):.1f}  médiane {st.median(v):.1f}  max {max(v):.1f}")
    else: print(f"{nom:18s}: aucune valeur ({nul} vides)")
print("échantillon :", [ (round(r['_t'],1), r.get('distance_cm'), r.get('temp_peau')) for r in rows[::max(1, len(rows)//8)] ])
