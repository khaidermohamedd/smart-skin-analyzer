/*
 * Diagnostic du câblage (Arduino Uno) - à téléverser temporairement en cas de capteur « null ».
 * Toutes les 3 s, envoie sur le port série (115200) :
 *   - rappel_SDA / rappel_SCL : le module MLX90614 (GY-906) tire ces fils vers son alimentation.
 *     1 = module branché ET alimenté ; 0 = pas d'alimentation, fil débranché ou mauvaise broche.
 *   - rappel_D2 : la résistance 10 kΩ du DHT22 tire DATA vers l'alimentation (même principe).
 *   - i2c : adresses qui répondent sur le bus (le MLX90614 répond en 0x5A).
 *   - dht : lecture du DHT22 (température / humidité ou "echec").
 *   - A0 : valeur brute de l'entrée du capteur de distance (aléatoire si rien n'est branché).
 */
#include <Wire.h>
#include "DHT.h"

DHT dht(2, DHT22);

// Une broche reliée à une résistance de rappel externe remonte à 1 tout de suite après avoir été
// forcée à 0 ; une broche « en l'air » reste à 0 un moment.
int rappelExterne(int pin) {
  pinMode(pin, OUTPUT);
  digitalWrite(pin, LOW);
  delay(2);
  pinMode(pin, INPUT);           // sans la résistance de rappel interne de l'Uno
  delayMicroseconds(200);
  return digitalRead(pin);
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println(F("{\"diagnostic\":\"demarrage\"}"));
}

void loop() {
  int sda = rappelExterne(A4), scl = rappelExterne(A5), d2 = rappelExterne(2);

  Wire.begin();
  String adresses = "";
  for (byte a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      if (adresses.length()) adresses += ",";
      adresses += "\"0x" + String(a, HEX) + "\"";
    }
  }
  Wire.end();

  dht.begin();
  delay(2100);
  float t = dht.readTemperature(), h = dht.readHumidity();

  Serial.print(F("{\"rappel_SDA\":")); Serial.print(sda);
  Serial.print(F(",\"rappel_SCL\":")); Serial.print(scl);
  Serial.print(F(",\"rappel_D2\":")); Serial.print(d2);
  Serial.print(F(",\"i2c\":[")); Serial.print(adresses); Serial.print(F("]"));
  Serial.print(F(",\"dht\":"));
  if (isnan(t) || isnan(h)) Serial.print(F("\"echec\""));
  else { Serial.print(F("{\"t\":")); Serial.print(t, 1); Serial.print(F(",\"h\":")); Serial.print(h, 1); Serial.print(F("}")); }
  Serial.print(F(",\"A0\":")); Serial.print(analogRead(A0));
  Serial.println(F("}"));
  delay(800);
}
