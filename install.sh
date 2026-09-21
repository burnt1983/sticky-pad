#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
BIN="${HOME}/.local/bin"
SHARE="${HOME}/.local/share/sticky-pad"
APPS="${HOME}/.local/share/applications"
AUTO="${HOME}/.config/autostart"
UNIT="${HOME}/.config/systemd/user"

mkdir -p "$BIN" "$SHARE" "$APPS" "$AUTO" "$UNIT"
install -m 0755 "$ROOT/sticky_pad.py" "$SHARE/sticky_pad.py"
ln -sfn "$SHARE/sticky_pad.py" "$BIN/sticky-pad"
ln -sfn "$SHARE/sticky_pad.py" "$BIN/lee-stickypad-widget"

sed "s|^Exec=sticky-pad$|Exec=${BIN}/sticky-pad|" \
    "$ROOT/data/sticky-pad.desktop" > "$APPS/sticky-pad.desktop"
cp "$APPS/sticky-pad.desktop" "$AUTO/sticky-pad.desktop"
chmod 0755 "$APPS/sticky-pad.desktop" "$AUTO/sticky-pad.desktop"

install -m 0644 "$ROOT/data/sticky-pad.service" "$UNIT/sticky-pad.service"

# Draw the yellow-pad icon on first launch.
python3 - << 'PY'
from pathlib import Path
import sys
sys.path.insert(0, str(Path.home() / ".local/share/sticky-pad"))
from sticky_pad import write_icon
icon = Path.home() / ".local/share/icons/hicolor/256x256/apps/lee-stickypad.png"
write_icon(icon, 256)
print("icon", icon)
PY

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f "${HOME}/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi
if command -v systemctl >/dev/null 2>&1; then
  systemctl --user daemon-reload
  systemctl --user enable --now sticky-pad.service >/dev/null 2>&1 || true
fi

if [ -d "$ROOT/cinnamon" ]; then
  mkdir -p "${HOME}/.local/share/cinnamon/desklets" "${HOME}/.local/share/cinnamon/applets"
  cp -a "$ROOT/cinnamon/desklets/." "${HOME}/.local/share/cinnamon/desklets/"
  cp -a "$ROOT/cinnamon/applets/." "${HOME}/.local/share/cinnamon/applets/"
fi

echo "Installed Sticky Pad."
echo "  Desklet:  sticky-pad --desklet"
echo "  Panel:    sticky-pad --panel"
echo "  Notes:    ~/.config/lee-stickypad/notes.json"
echo "Cinnamon: Desklets → Sticky Pad. Ctrl+N new page."
