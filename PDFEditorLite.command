#!/bin/sh
# PDF Editor Lite - chay tren Linux Mint / macOS. Lan dau se tu cai thu vien vao thu muc .venv ben canh.
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  echo "Lan dau chay: dang cai thu vien, can co mang, mat vai phut..."
  if ! python3 -m venv .venv; then
    echo "Thieu Python hoac goi venv."
    echo "  Linux Mint: sudo apt install python3-venv libxcb-cursor0"
    echo "  macOS:      cai Python 3.11+ tu https://www.python.org/downloads/"
    exit 1
  fi
  .venv/bin/python -m pip install --upgrade pip
  if ! .venv/bin/python -m pip install -r requirements.txt; then
    echo "Cai thu vien that bai. Kiem tra mang roi chay lai."
    rm -rf .venv
    exit 1
  fi
  .venv/bin/python -m pip install pdf2docx || echo "[Canh bao] Khong cai duoc pdf2docx: chua dung duoc PDF sang Word."
  .venv/bin/python -m pip install python-pkcs11 || echo "[Canh bao] Khong cai duoc python-pkcs11: chua ky duoc bang USB token."
fi
exec .venv/bin/python main.py "$@"
