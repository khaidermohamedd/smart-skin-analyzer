/*
 * Smart Skin Analyzer - Firmware ESP32 (capteurs + LED)
 * ------------------------------------------------------
 * Lit les capteurs sans contact et les envoie au Raspberry Pi par le câble USB
 * (port série, 115200 bauds), une ligne JSON par mesure. Reçoit les ordres de LED.
 *
 * Câblage (voir docs/cablage) :
 *   Bus I2C partagé   SDA = GPIO21, SCL = GPIO22, alimentation 3V3
 *     - MLX90614 (température IR du visage)   adresse 0x5A
 *     - VL53L0X ou VL53L1X (distance)          adresse 0x29 (détection automatique)
 *   DHT22 (température + humidité de l'air)   DATA = GPIO4 (+ résistance 10 kΩ vers 3V3 si capteur nu)
 *   LED RGB simple                            R = GPIO25, G = GPIO26, B = GPIO27 (220 Ω sur chaque)
 *
 * Messages envoyés (une ligne JSON) :
 *   {"type":"hello","firmware":"...","capteurs":{"mlx":true,"tof":"VL53L0X","dht":true}}
 *   {"type":"mesure","ms":1234,"dist_mm":412,"t_visage":34.8,"t_ambiante_ir":24.1,"t_air":23.6,"humidite":41.2}
 *   (une valeur vaut null si le capteur est absent ou hors de portée)
 *
 * Commandes reçues (une ligne de texte) :
 *   LED <r> <g> <b>        couleur fixe, 0-255         ex. "LED 255 0 0"
 *   ETAT <nom>             animation : attente, detecte, analyse, ok, erreur, eteint
 *   PING                   répond {"type":"pong"}
 *   INFO                   renvoie le message hello
 *
 * Bibliothèques (Gestionnaire de bibliothèques de l'IDE Arduino) :
 *   Adafruit MLX90614 Library, DHT sensor library (Adafruit) + Adafruit Unified Sensor,
 *   VL53L0X (Pololu), VL53L1X (Pololu)
 * Carte : "ESP32 Dev Module" (paquet esp32 by Espressif Systems, version 3.x)
 */
#include <Wire.h>
#include <Adafruit_MLX90614.h>
#include <DHT.h>
#include <VL53L0X.h>
#include <VL53L1X.h>

// ---------------- Configuration ----------------
#define FIRMWARE        "skin-esp32 1.0"
#define PIN_SDA         21
#define PIN_SCL         22
#define PIN_DHT         4
#define PIN_LED_R       25
#define PIN_LED_G       26
#define PIN_LED_B       27
#define LED_ANODE_COMMUNE 0     // 1 si la patte commune (la plus longue) de la LED va au 3V3, 0 si elle va au GND

const uint32_t PERIODE_MESURE_MS = 200;    // envoi 5 fois par seconde
const uint32_t PERIODE_TEMP_MS   = 1000;   // MLX90614 : 1 fois par seconde suffit
const uint32_t PERIODE_DHT_MS    = 2500;   // DHT22 : pas plus d'une lecture toutes les 2 s
const uint16_t DIST_MAX_MM       = 2000;   // au-delà : "personne"

// ---------------- Capteurs ----------------
Adafruit_MLX90614 mlx;
DHT dht(PIN_DHT, DHT22);
VL53L0X tof0;
VL53L1X tof1;

bool  mlxOk = false, dhtOk = false;
int   tofType = 0;                 // 0 = absent, 1 = VL53L0X, 2 = VL53L1X
float tVisage = NAN, tAmbIr = NAN, tAir = NAN, hum = NAN;
int   distMm = -1;
uint32_t tMesure = 0, tTemp = 0, tDht = 0;

// ---------------- LED ----------------
enum Etat { ATTENTE, DETECTE, ANALYSE, OK_, ERREUR, ETEINT, FIXE };
Etat etat = ATTENTE;
uint8_t fixR = 0, fixG = 0, fixB = 0;
uint32_t tEtat = 0;

void ledBrute(uint8_t r, uint8_t g, uint8_t b) {
#if LED_ANODE_COMMUNE
  r = 255 - r; g = 255 - g; b = 255 - b;
#endif
  ledcWrite(PIN_LED_R, r);
  ledcWrite(PIN_LED_G, g);
  ledcWrite(PIN_LED_B, b);
}

// Respiration douce : intensité 0..1 avec une période donnée
float respiration(uint32_t periodeMs) {
  float ph = (millis() % periodeMs) / (float)periodeMs;
  return 0.5f - 0.5f * cosf(2.0f * PI * ph);
}

void majLed() {
  uint32_t dt = millis() - tEtat;
  switch (etat) {
    case ATTENTE: { float k = 0.08f + 0.25f * respiration(4000); ledBrute(255 * k, 255 * k, 255 * k); break; }  // blanc doux
    case DETECTE: ledBrute(0, 90, 255); break;                                                               // bleu
    case ANALYSE: { float k = 0.15f + 0.85f * respiration(1200); ledBrute(140 * k, 0, 255 * k); break; }    // violet pulsé
    case OK_:     ledBrute(0, 255, 60); if (dt > 5000) etat = ATTENTE; break;                               // vert 5 s
    case ERREUR:  ledBrute(((dt / 250) % 2) ? 255 : 0, 0, 0); if (dt > 3000) etat = ATTENTE; break;         // rouge clignotant 3 s
    case ETEINT:  ledBrute(0, 0, 0); break;
    case FIXE:    ledBrute(fixR, fixG, fixB); break;
  }
}

// ---------------- JSON ----------------
// Ajoute "cle":valeur (ou null si NAN) au tampon
void jsonNombre(String &s, const char *cle, float v, int dec) {
  s += '"'; s += cle; s += "\":";
  if (isnan(v)) s += "null"; else s += String(v, dec);
}

void envoyerHello() {
  String s = "{\"type\":\"hello\",\"firmware\":\"" FIRMWARE "\",\"capteurs\":{\"mlx\":";
  s += mlxOk ? "true" : "false";
  s += ",\"tof\":";
  s += tofType == 1 ? "\"VL53L0X\"" : tofType == 2 ? "\"VL53L1X\"" : "null";
  s += ",\"dht\":";
  s += dhtOk ? "true" : "false";
  s += "}}";
  Serial.println(s);
}

void envoyerMesure() {
  String s = "{\"type\":\"mesure\",\"ms\":";
  s += millis();
  s += ",\"dist_mm\":";
  if (distMm < 0) s += "null"; else s += distMm;
  s += ',';  jsonNombre(s, "t_visage", tVisage, 2);
  s += ',';  jsonNombre(s, "t_ambiante_ir", tAmbIr, 2);
  s += ',';  jsonNombre(s, "t_air", tAir, 1);
  s += ',';  jsonNombre(s, "humidite", hum, 1);
  s += '}';
  Serial.println(s);
}

// ---------------- Initialisation ----------------
void initTof() {
  // Les deux modèles répondent à l'adresse 0x29 : on essaie le VL53L0X puis le VL53L1X
  tof0.setTimeout(100);
  if (tof0.init()) {
    tof0.setMeasurementTimingBudget(50000);
    tof0.startContinuous(60);
    tofType = 1;
    return;
  }
  tof1.setTimeout(100);
  if (tof1.init()) {
    tof1.setDistanceMode(VL53L1X::Medium);
    tof1.setMeasurementTimingBudget(50000);
    tof1.startContinuous(60);
    tofType = 2;
  }
}

void setup() {
  Serial.begin(115200);
  ledcAttach(PIN_LED_R, 5000, 8);
  ledcAttach(PIN_LED_G, 5000, 8);
  ledcAttach(PIN_LED_B, 5000, 8);
  ledBrute(0, 0, 0);

  Wire.begin(PIN_SDA, PIN_SCL);
  Wire.setClock(100000);          // le MLX90614 ne supporte pas plus de 100 kHz
  mlxOk = mlx.begin(MLX90614_I2CADDR, &Wire);
  initTof();
  dht.begin();
  delay(2000);                    // le DHT22 a besoin de ~2 s après la mise sous tension
  dhtOk = !isnan(dht.readTemperature());

  // Petit test des 3 couleurs au démarrage (vérifie le câblage de la LED)
  ledBrute(255, 0, 0); delay(250);
  ledBrute(0, 255, 0); delay(250);
  ledBrute(0, 0, 255); delay(250);
  ledBrute(0, 0, 0);

  envoyerHello();
  tEtat = millis();
}

// ---------------- Lecture des commandes ----------------
String ligne;

void traiterCommande(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;
  String haut = cmd; haut.toUpperCase();
  if (haut == "PING") { Serial.println("{\"type\":\"pong\"}"); return; }
  if (haut == "INFO") { envoyerHello(); return; }
  if (haut.startsWith("LED ")) {
    int r, g, b;
    if (sscanf(cmd.c_str() + 4, "%d %d %d", &r, &g, &b) == 3) {
      fixR = constrain(r, 0, 255); fixG = constrain(g, 0, 255); fixB = constrain(b, 0, 255);
      etat = FIXE; tEtat = millis();
      return;
    }
  }
  if (haut.startsWith("ETAT ")) {
    String e = haut.substring(5); e.trim();
    Etat n = etat;
    if (e == "ATTENTE") n = ATTENTE;
    else if (e == "DETECTE") n = DETECTE;
    else if (e == "ANALYSE") n = ANALYSE;
    else if (e == "OK") n = OK_;
    else if (e == "ERREUR") n = ERREUR;
    else if (e == "ETEINT") n = ETEINT;
    else { Serial.println("{\"type\":\"erreur\",\"message\":\"etat inconnu\"}"); return; }
    etat = n; tEtat = millis();
    return;
  }
  Serial.println("{\"type\":\"erreur\",\"message\":\"commande inconnue\"}");
}

void lireSerie() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') { traiterCommande(ligne); ligne = ""; }
    else if (ligne.length() < 64) ligne += c;
  }
}

// ---------------- Boucle principale ----------------
void lireDistance() {
  if (tofType == 1) {
    uint16_t d = tof0.readRangeContinuousMillimeters();
    distMm = (tof0.timeoutOccurred() || d == 0 || d > DIST_MAX_MM) ? -1 : d;
  } else if (tofType == 2) {
    if (tof1.dataReady()) {
      uint16_t d = tof1.read(false);
      bool valide = tof1.ranging_data.range_status == VL53L1X::RangeValid;
      distMm = (!valide || d == 0 || d > DIST_MAX_MM) ? -1 : d;
    }
  }
}

void loop() {
  uint32_t now = millis();
  lireSerie();
  majLed();

  if (now - tTemp >= PERIODE_TEMP_MS && mlxOk) {
    tTemp = now;
    tVisage = mlx.readObjectTempC();
    tAmbIr = mlx.readAmbientTempC();
    if (tVisage < -40 || tVisage > 120) tVisage = NAN;     // lecture aberrante (bus I2C perturbé)
  }
  if (now - tDht >= PERIODE_DHT_MS) {
    tDht = now;
    float t = dht.readTemperature(), h = dht.readHumidity();
    if (!isnan(t) && !isnan(h)) { tAir = t; hum = h; dhtOk = true; }
  }
  if (now - tMesure >= PERIODE_MESURE_MS) {
    tMesure = now;
    lireDistance();
    envoyerMesure();
  }
}
