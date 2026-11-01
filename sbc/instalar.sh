#!/usr/bin/env bash
# Instala o actualiza el software del osciloscopio en la Raspberry Pi.
# Uso (desde cualquier carpeta):  bash sbc/instalar.sh
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"     # raiz del repositorio
USUARIO="$(id -un)"
echo "Repositorio: $RAIZ | Usuario del servicio: $USUARIO"

echo "== 1/5 Paquetes =="
sudo apt install -y python3-spidev python3-libgpiod python3-flask nginx

echo "== 2/5 SPI0 =="
sudo raspi-config nonint do_spi 0

echo "== 3/5 Dashboard =="
sudo mkdir -p /var/www/osciloscopio
sudo cp "$RAIZ/sbc/web/index.html" /var/www/osciloscopio/

echo "== 4/5 nginx =="
sudo cp "$RAIZ/sbc/nginx/osciloscopio.conf" /etc/nginx/sites-available/osciloscopio
sudo ln -sf /etc/nginx/sites-available/osciloscopio /etc/nginx/sites-enabled/osciloscopio
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

echo "== 5/5 Servicio del backend =="
sed -e "s|/home/sebastian/osciloscopio-spi|$RAIZ|" -e "s|^User=sebastian|User=$USUARIO|" \
    "$RAIZ/sbc/systemd/osciloscopio-backend.service" \
    | sudo tee /etc/systemd/system/osciloscopio-backend.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable osciloscopio-backend
sudo systemctl restart osciloscopio-backend

sleep 3
systemctl is-active osciloscopio-backend
echo "Listo. Dashboard en http://$(hostname).local"
