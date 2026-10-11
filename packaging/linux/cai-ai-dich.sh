#!/usr/bin/env bash
# Thanh phan tuy chon: AI dich chay ngay tren may (Ollama + model dich). Tuong duong muc "AI dich chay tren may" cua bo cai Windows.
MODEL="${1:-gemma3:4b}"
echo "=== PDF Editor Lite: cai AI dich chay tren may ==="
echo "Se tai Ollama (~1,5 GB) va model $MODEL (~3,3 GB). Can mang Internet; may nen co RAM tu 8 GB."
read -r -p "Tiep tuc? [c/K] " a
case "$a" in c|C|y|Y) ;; *) echo "Da huy."; sleep 2; exit 0;; esac
if ! command -v ollama >/dev/null 2>&1; then
  command -v curl >/dev/null 2>&1 || sudo apt-get install -y curl
  curl -fsSL https://ollama.com/install.sh | sh || { echo "Chua cai duoc Ollama. Kiem tra mang roi chay lai."; read -r -p "Nhan Enter de dong..." _; exit 1; }
fi
(ollama list >/dev/null 2>&1) || { (ollama serve >/dev/null 2>&1 &); sleep 5; }
if ollama pull "$MODEL"; then
  echo; echo "XONG. Mo PDF Editor Lite > Dich tai lieu, chon bo may 'AI khac theo chuan OpenAI' > 'Ollama tren may nay'."
else
  echo; echo "Chua tai duoc model. Chay lai muc nay khi co mang."
fi
read -r -p "Nhan Enter de dong..." _
