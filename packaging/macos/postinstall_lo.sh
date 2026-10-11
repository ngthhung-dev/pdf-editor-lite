#!/bin/sh
# Cai LibreOffice kem theo bo cai (bo qua neu may da co).
[ -d "/Applications/LibreOffice.app" ] && exit 0
D="$(cd "$(dirname "$0")" && pwd)"
M="$(mktemp -d /tmp/pdfel-lo.XXXXXX)"
if hdiutil attach "$D/LibreOffice.dmg" -nobrowse -readonly -noverify -mountpoint "$M" >/dev/null 2>&1; then
  ditto "$M/LibreOffice.app" "/Applications/LibreOffice.app"
  hdiutil detach "$M" -force >/dev/null 2>&1
  xattr -dr com.apple.quarantine "/Applications/LibreOffice.app" 2>/dev/null
fi
rmdir "$M" 2>/dev/null
exit 0
