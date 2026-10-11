#!/usr/bin/env bash
# Build goi cai .deb cho Linux Mint / Ubuntu / Debian (64-bit).
#   bash packaging/linux/build_linux.sh
# Can tren may build: Python 3.10+, python3-venv, dpkg-deb, curl, mang Internet. Nen build tren Ubuntu 22.04 de chay duoc ca Mint 21 va 22.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$ROOT/build_linux"; VENDOR="$WORK/vendor"; DIST="$WORK/dist/PDFEditorLite"; OUT="$WORK/output"
VER="1.0.0"; BUILD="${LITEPDF_BUILD:-0}"
mkdir -p "$WORK" "$VENDOR" "$OUT"
LOG="$WORK/build.log"; echo "Build PDF Editor Lite (Linux) - $(date '+%F %T')" > "$LOG"
step() { echo; echo "=== $1 ==="; echo "$(date +%T)  $1" >> "$LOG"; }
note() { echo "  $1"; echo "  $(date +%T)  $1" >> "$LOG"; }
trap 'echo "LOI o dong $LINENO" >> "$LOG"' ERR

step "1/6  Python va thu vien"
PY="${PYTHON:-python3}"
[ -x "$WORK/venv/bin/python" ] || "$PY" -m venv "$WORK/venv"
VPY="$WORK/venv/bin/python"
"$VPY" -m pip install -q --upgrade pip
"$VPY" -m pip install -q -r "$ROOT/requirements.txt"; note "thu vien chinh: OK"
for pkg in pdf2docx python-pkcs11 rapidocr onnxruntime pyinstaller; do
  if "$VPY" -m pip install -q "$pkg"; then note "$pkg : OK"; else
    [ "$pkg" = pyinstaller ] && { echo "Khong cai duoc PyInstaller"; exit 1; }
    note "KHONG cai duoc $pkg : chuc nang tuong ung se thieu."; fi
done

step "2/6  Model tieng Viet/Latin cua RapidOCR"
(cd "$ROOT" && timeout 300 "$VPY" -c "from litepdf import ocr; ocr.rapid_engine('latin', ''); print('ok')") \
  && note "model latin: OK" || note "Chua tai duoc model latin: app se tu tai o lan dung dau."

step "3/6  Du lieu ngon ngu Tesseract (vie, eng, osd)"
mkdir -p "$VENDOR/tessdata"
for l in vie eng osd; do
  f="$VENDOR/tessdata/$l.traineddata"
  [ -s "$f" ] || curl -L --fail -sS --retry 3 -o "$f" "https://github.com/tesseract-ocr/tessdata_fast/raw/main/$l.traineddata"
done
note "tessdata: $(ls "$VENDOR/tessdata" | tr '\n' ' ')"

step "4/6  Dong goi app bang PyInstaller"
rm -rf "$WORK/dist"
LITEPDF_TESSDATA="$VENDOR/tessdata" "$VPY" -m PyInstaller "$ROOT/packaging/PDFEditorLite.spec" --noconfirm \
  --distpath "$WORK/dist" --workpath "$WORK/pyi" >> "$WORK/pyinstaller.log" 2>&1 || { tail -40 "$WORK/pyinstaller.log" | tee -a "$LOG"; exit 1; }
[ -x "$DIST/PDFEditorLite" ] || { echo "PyInstaller that bai"; exit 1; }
note "dung luong ban dong goi: $(du -sm "$DIST" | cut -f1) MB"

step "5/6  Tao goi .deb"
PKG="$WORK/deb"; rm -rf "$PKG"
mkdir -p "$PKG/DEBIAN" "$PKG/opt" "$PKG/usr/bin" "$PKG/usr/share/applications" "$PKG/usr/share/icons/hicolor/256x256/apps"
cp -a "$DIST" "$PKG/opt/pdf-editor-lite"
install -m 755 "$ROOT/packaging/linux/cai-ai-dich.sh" "$PKG/opt/pdf-editor-lite/cai-ai-dich.sh"
ln -s /opt/pdf-editor-lite/PDFEditorLite "$PKG/usr/bin/pdf-editor-lite"
install -m 644 "$ROOT/assets/app_icon.png" "$PKG/usr/share/icons/hicolor/256x256/apps/pdf-editor-lite.png"
install -m 644 "$ROOT/packaging/linux/pdf-editor-lite.desktop" "$ROOT/packaging/linux/pdf-editor-lite-ai.desktop" "$PKG/usr/share/applications/"
SIZE=$(du -sk "$PKG/opt" | cut -f1)
sed -e "s/@VER@/$VER-$BUILD/" -e "s/@SIZE@/$SIZE/" "$ROOT/packaging/linux/control" > "$PKG/DEBIAN/control"
install -m 755 "$ROOT/packaging/linux/postinst" "$PKG/DEBIAN/postinst"
install -m 755 "$ROOT/packaging/linux/postinst" "$PKG/DEBIAN/postrm"
DEB="$OUT/pdf-editor-lite_${VER}-build${BUILD}_amd64.deb"
dpkg-deb --build --root-owner-group -Zxz "$PKG" "$DEB" >> "$LOG"
note "XONG: $(basename "$DEB")  $(du -m "$DEB" | cut -f1) MB"

step "6/6  Tu kiem tra ban dong goi"
ST="$WORK/selftest.json"; rm -f "$ST"
QT_QPA_PLATFORM=offscreen timeout 300 "$DIST/PDFEditorLite" --selftest "$ST" || true
[ -s "$ST" ] || { echo "Ban dong goi khong chay duoc (khong co selftest.json)" | tee -a "$LOG"; exit 1; }
cat "$ST"; cat "$ST" >> "$LOG"
if grep -Eq '"(pymupdf|pyhanko|fonts)": "LOI' "$ST"; then echo "Thieu thanh phan bat buoc"; exit 1; fi
echo; echo "XONG. File cai: $DEB"
