#!/usr/bin/env bash
set -euo pipefail
systemctl --user disable --now sticky-pad.service >/dev/null 2>&1 || true
rm -f \
  "${HOME}/.local/bin/sticky-pad" \
  "${HOME}/.local/bin/lee-stickypad-widget" \
  "${HOME}/.local/share/applications/sticky-pad.desktop" \
  "${HOME}/.config/autostart/sticky-pad.desktop" \
  "${HOME}/.config/systemd/user/sticky-pad.service"
rm -rf "${HOME}/.local/share/sticky-pad"
echo "Removed Sticky Pad. Notes in ~/.config/lee-stickypad were left in place."
