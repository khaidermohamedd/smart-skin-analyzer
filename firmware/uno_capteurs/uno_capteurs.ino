/*
 * Smart Skin Analyzer - Firmware ARDUINO UNO (capteurs + LED)
 * -----------------------------------------------------------
 * Adapté du firmware de J. Salek (https://github.com/jihanesalek263-png/SmartSkinAnalyzer,
 * smartskin_uno.ino). MÊME format JSON, donc son lire_capteurs.py fonctionne toujours :
 *   {"distance_cm":18.3,"temp_peau":33.4,"temp_air":24.1,"humidite":46.2}
 *
 * Changements pour le miroir :
 *   - envoi 4 fois par seconde (au lieu de toutes les 2 s) pour guider la personne en direct ;
 *     le DHT22 reste lu toutes les 2,5 s (il ne peut pas aller plus vite), sa valeur est répétée ;
 *   - pilotage de la LED RGB par le Raspberry Pi (commandes "ETAT ..." et "LED r g b").
 *
 * BRANCHEMENTS (Arduino Uno) :
 *   MLX90614 : VIN -> 3.3V (jamais 5V sur un capteur nu) | GND -> GND | SDA -> A4 | SCL -> A5
 *   DHT22    : patte 1 (VCC) -> 5V | patte 2 (DATA) -> D2 | patte 4 (GND) -> GND
 *              + résistance 10 kΩ entre la patte 1 et la patte 2
 *   Sharp IR GP2Y0A21 : rouge -> 5V | noir -> GND | jaune -> A0
 *   LED RGB  : R -> D9, G -> D10, B -> D11, chacune via une résistance de 220 Ω ;
 *              patte commune (la plus longue) -> GND (ou 5V : mettre LED_ANODE_COMMUNE à 1)
 *
 * Commandes reçues (une ligne, 115200 bauds) :
 *   ETAT ATTENTE | DETECTE | ANALYSE | OK | ERREUR | ETEINT      LED r g b      PING
 *
 * Bibliothèques : DHT sensor library + Adafruit Unified Sensor, Adafruit MLX90614 Library.
 */
#include <Wire.h>
#include <Adafruit_MLX90614.h>
#include "DHT.h"

#define PIN_DHT    2
#define PIN_SHARP  A0
#define PIN_LED_R  9
#define PIN_LED_G  10
#define PIN_LED_B  11
#define LED_ANODE_COMMUNE 0

const unsigned long PERIODE_ENVOI_MS = 250;
const unsigned long PERIODE_DHT_MS   = 2500;

DHT dht(PIN_DHT, DHT22);
Adafruit_MLX90614 mlx = Adafruit_MLX90614();
bool mlxOk = false;
float tempAir = NAN, humidite = NAN;
unsigned long tEnvoi = 0, tDht = 0, tEtat = 0;

enum Etat { ATTENTE, DETECTE, ANALYSE, OK_, ERREUR, ETEINT, FIXE };
Etat etat = ATTENTE;
byte fixR = 0, fixG = 0, fixB = 0;

// ---------------- Capteurs ----------------
// Distance en cm avec un Sharp GP2Y0A21 (portée 10-80 cm) - formule du firmware d'origine.
float lireDistanceCm() {
  long somme = 0;
  for (int i = 0; i < 10; i++) {            // moyenne de 10 mesures (réduit le bruit)
    somme += analogRead(PIN_SHARP);
    delay(2);
  }
  float volts = (somme / 10.0) * 5.0 / 1023.0;
  if (volts < 0.4) return NAN;               // rien devant le capteur / trop loin
  return 29.988 * pow(volts, -1.173);
}

void afficherValeur(const char* nom, float v, bool dernier = false) {
  Serial.print("\""); Serial.print(nom); Serial.print("\":");
  if (isnan(v)) Serial.print("null");
  else Serial.print(v, 1);
  if (!dernier) Serial.print(",");
}

// ---------------- LED ----------------
void ledBrute(byte r, byte g, byte b) {
#if LED_ANODE_COMMUNE
  r = 255 - r; g = 255 - g; b = 255 - b;
#endif
  analogWrite(PIN_LED_R, r);
  analogWrite(PIN_LED_G, g);
  analogWrite(PIN_LED_B, b);
}

float respiration(unsigned long periodeMs) {
  float ph = (millis() % periodeMs) / (float)periodeMs;
  return 0.5 - 0.5 * cos(2.0 * PI * ph);
}

void majLed() {
  unsigned long dt = millis() - tEtat;
  switch (etat) {
    case ATTENTE: { float k = 0.08 + 0.25 * respiration(4000); ledBrute(255 * k, 255 * k, 255 * k); break; }
    case DETECTE: ledBrute(0, 90, 255); break;
    case ANALYSE: { float k = 0.15 + 0.85 * respiration(1200); ledBrute(140 * k, 0, 255 * k); break; }
    case OK_:     ledBrute(0, 255, 60); if (dt > 5000) etat = ATTENTE; break;
    case ERREUR:  ledBrute(((dt / 250) % 2) ? 255 : 0, 0, 0); if (dt > 3000) etat = ATTENTE; break;
    case ETEINT:  ledBrute(0, 0, 0); break;
    case FIXE:    ledBrute(fixR, fixG, fixB); break;
  }
}

// ---------------- Commandes du Raspberry Pi ----------------
char ligne[40];
byte nLigne = 0;

void traiterCommande() {
  ligne[nLigne] = '\0';
  for (byte i = 0; i < nLigne; i++) ligne[i] = toupper(ligne[i]);
  int r, g, b;
  if (strcmp(ligne, "PING") == 0) { Serial.println("{\"type\":\"pong\"}"); }
  else if (strncmp(ligne, "LED ", 4) == 0 && sscanf(ligne + 4, "%d %d %d", &r, &g, &b) == 3) {
    fixR = constrain(r, 0, 255); fixG = constrain(g, 0, 255); fixB = constrain(b, 0, 255);
    etat = FIXE; tEtat = millis();
  }
  else if (strncmp(ligne, "ETAT ", 5) == 0) {
    const char* e = ligne + 5;
    if      (!strcmp(e, "ATTENTE")) etat = ATTENTE;
    else if (!strcmp(e, "DETECTE")) etat = DETECTE;
    else if (!strcmp(e, "ANALYSE")) etat = ANALYSE;
    else if (!strcmp(e, "OK"))      etat = OK_;
    else if (!strcmp(e, "ERREUR"))  etat = ERREUR;
    else if (!strcmp(e, "ETEINT"))  etat = ETEINT;
    tEtat = millis();
  }
  nLigne = 0;
}

void lireSerie() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') { if (nLigne) traiterCommande(); }
    else if (nLigne < sizeof(ligne) - 1) ligne[nLigne++] = c;
  }
}

// ---------------- Programme ----------------
void setup() {
  Serial.begin(115200);
  pinMode(PIN_LED_R, OUTPUT); pinMode(PIN_LED_G, OUTPUT); pinMode(PIN_LED_B, OUTPUT);
  ledBrute(255, 0, 0); delay(250);           // test de la LED : rouge, vert, bleu
  ledBrute(0, 255, 0); delay(250);
  ledBrute(0, 0, 255); delay(250);
  ledBrute(0, 0, 0);
  dht.begin();
  mlxOk = mlx.begin();
  if (!mlxOk) {
    Serial.println("{\"erreur\":\"MLX90614 non detecte (verifie SDA/SCL/alim)\"}");
  }
  tEtat = millis();
}

void loop() {
  unsigned long now = millis();
  lireSerie();
  majLed();

  if (now - tDht >= PERIODE_DHT_MS) {        // le DHT22 ne se lit pas plus vite que ~2 s
    tDht = now;
    float t = dht.readTemperature(), h = dht.readHumidity();
    if (!isnan(t) && !isnan(h)) { tempAir = t; humidite = h; }
  }
  if (now - tEnvoi >= PERIODE_ENVOI_MS) {
    tEnvoi = now;
    float distance = lireDistanceCm();
    float tempPeau = mlxOk ? mlx.readObjectTempC() : NAN;
    Serial.print("{");
    afficherValeur("distance_cm", distance);
    afficherValeur("temp_peau", tempPeau);
    afficherValeur("temp_air", tempAir);
    afficherValeur("humidite", humidite, true);
    Serial.println("}");
  }
}
