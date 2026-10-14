#!/usr/bin/env bash
# Compile le firmware ESP32 sous Linux (WSL) pour vérifier qu'il n'y a pas d'erreur.
#   wsl -d skinai -u root -- bash /mnt/d/skin_ai/code/firmware/compile_check.sh
set -e
export ARDUINO_DIRECTORIES_DATA=/data/arduino ARDUINO_DIRECTORIES_USER=/data/arduino/user
if ! command -v arduino-cli >/dev/null; then
  curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | BINDIR=/usr/local/bin sh
fi
arduino-cli config init --overwrite >/dev/null
arduino-cli config add board_manager.additional_urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli core update-index
arduino-cli core install esp32:esp32
arduino-cli lib install "Adafruit MLX90614 Library" "DHT sensor library" "Adafruit Unified Sensor" "VL53L0X" "VL53L1X"
mkdir -p /tmp/fw && cp -r /mnt/d/skin_ai/code/firmware/esp32_capteurs /tmp/fw/
arduino-cli compile --fqbn esp32:esp32:esp32 /tmp/fw/esp32_capteurs 2>&1 | tail -8
