#!/usr/bin/env bash
# Thành phần tuỳ chọn: AI dịch chạy ngay trên máy (Ollama + model dịch), tương đương mục "AI dịch chạy trên máy" của bộ cài Windows.
MODEL="${1:-gemma3:4b}"
echo "=== PDF Editor Lite: cài AI dịch chạy trên máy ==="
echo "Sẽ tải Ollama (~1,5 GB) và model $MODEL (~3,3 GB). Cần mạng Internet; máy nên có RAM từ 8 GB."
read -r -p "Tiếp tục? [c/K] " a
case "$a" in c|C|y|Y) ;; *) echo "Đã huỷ."; sleep 2; exit 0;; esac
if ! command -v ollama >/dev/null 2>&1; then
  command -v curl >/dev/null 2>&1 || sudo apt-get install -y curl
  curl -fsSL https://ollama.com/install.sh | sh || { echo "Chưa cài được Ollama. Kiểm tra mạng rồi chạy lại."; read -r -p "Nhấn Enter để đóng..." _; exit 1; }
fi
(ollama list >/dev/null 2>&1) || { (ollama serve >/dev/null 2>&1 &); sleep 5; }
if ollama pull "$MODEL"; then
  echo; echo "XONG. Mở PDF Editor Lite > Dịch tài liệu, chọn bộ máy 'AI khác theo chuẩn OpenAI' > 'Ollama trên máy này'."
else
  echo; echo "Chưa tải được model. Chạy lại mục này khi có mạng."
fi
read -r -p "Nhấn Enter để đóng..." _
