#!/bin/sh
# Thanh phan tuy chon: tai va cai Ollama + model dich (can mang). Loi o day khong lam hong viec cai app.
U="$(stat -f%Su /dev/console 2>/dev/null)"; [ -n "$U" ] && [ "$U" != root ] || U="$USER"
LOGF="/tmp/pdf-editor-lite-ai.log"; : > "$LOGF"
if [ ! -d "/Applications/Ollama.app" ]; then
  T="$(mktemp -d /tmp/pdfel-ai.XXXXXX)"
  if curl -L --fail -sS --retry 3 --max-time 3000 -o "$T/Ollama.zip" "https://ollama.com/download/Ollama-darwin.zip" >> "$LOGF" 2>&1; then
    ditto -x -k "$T/Ollama.zip" "/Applications/" >> "$LOGF" 2>&1
    chown -R "$U" "/Applications/Ollama.app" 2>/dev/null
    xattr -dr com.apple.quarantine "/Applications/Ollama.app" 2>/dev/null
  fi
  rm -rf "$T"
fi
OL="/Applications/Ollama.app/Contents/Resources/ollama"
if [ -x "$OL" ] && [ ! -f /tmp/pdfel_skip_model ]; then
  sudo -H -u "$U" sh -c "('$OL' list >/dev/null 2>&1) || { '$OL' serve >/dev/null 2>&1 & sleep 6; }; '$OL' pull @MODEL@" >> "$LOGF" 2>&1
  sudo -H -u "$U" open -g -a Ollama >> "$LOGF" 2>&1
fi
exit 0
