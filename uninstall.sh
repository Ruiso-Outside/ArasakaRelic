#!/usr/bin/env bash
# ARASAKA RELIC // desinstalador. Os backups que voce ja fez NAO sao apagados (ficam no destino escolhido).
set -uo pipefail
APP_ID=arasaka-relic
DATA="${XDG_DATA_HOME:-$HOME/.local/share}/$APP_ID"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
UNITS="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
systemctl --user disable --now "$APP_ID.timer" >/dev/null 2>&1
rm -f "$UNITS/$APP_ID.timer" "$UNITS/$APP_ID.service"
systemctl --user daemon-reload >/dev/null 2>&1
rm -f "$HOME/.local/bin/$APP_ID" "$APPS/$APP_ID.desktop" \
      "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps/$APP_ID.svg" \
      "${XDG_DATA_HOME:-$HOME/.local/share}/icons/Arasaka/scalable/apps/$APP_ID.svg"
rm -rf "$DATA/app" "$DATA/venv"
update-desktop-database -q "$APPS" 2>/dev/null
echo "■ Arasaka Relic removido. Os seus backups continuam no destino; as configuracoes ficam em ~/.config/$APP_ID."
