#!/usr/bin/env bash
# Build bo cai .pkg cho macOS (chay tren may Mac; kien truc theo may build: Apple Silicon hoac Intel).
#   bash packaging/macos/build_macos.sh           tuy chon: NO_LIBREOFFICE=1 de khong kem LibreOffice
# Can: Python 3.10+ (python.org hoac Homebrew), Xcode Command Line Tools, mang Internet.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$ROOT/build_mac"; VENDOR="$WORK/vendor"; OUT="$WORK/output"
VER="1.0.0"; BUILD="${LITEPDF_BUILD:-0}"; MODEL="${MODEL:-gemma3:4b}"
ARCH="$(uname -m)"; [ "$ARCH" = arm64 ] && { TAG="AppleSilicon"; LOARCH="aarch64"; LOFILE="aarch64"; HOSTS="arm64"; } \
                                   || { TAG="Intel"; LOARCH="x86_64"; LOFILE="x86-64"; HOSTS="x86_64,arm64"; }
mkdir -p "$WORK" "$VENDOR" "$OUT"
LOG="$WORK/build.log"; echo "Build PDF Editor Lite (macOS $ARCH) - $(date '+%F %T')" > "$LOG"
step() { echo; echo "=== $1 ==="; echo "$(date +%T)  $1" >> "$LOG"; }
note() { echo "  $1"; echo "  $(date +%T)  $1" >> "$LOG"; }
trap 'echo "LOI o dong $LINENO" >> "$LOG"' ERR

step "1/7  Python va thu vien"
PY="${PYTHON:-python3}"
[ -x "$WORK/venv/bin/python" ] || "$PY" -m venv "$WORK/venv"
VPY="$WORK/venv/bin/python"
"$VPY" -m pip install -q --upgrade pip
"$VPY" -m pip install -q --only-binary=:all: cryptography      # ban co san wheel (tu build se dinh libssl cua Homebrew, xung dot voi Python)
"$VPY" -m pip install -q --prefer-binary -r "$ROOT/requirements.txt"; note "thu vien chinh: OK ($("$VPY" -m pip list 2>/dev/null | grep -i -E '^(cryptography|opencv|onnxruntime|PySide6_Essentials|PyMuPDF) ' | tr -s ' ' | tr '\n' ',')"
for pkg in pdf2docx python-pkcs11 rapidocr onnxruntime pyinstaller; do
  if "$VPY" -m pip install -q "$pkg"; then note "$pkg : OK"; else
    [ "$pkg" = pyinstaller ] && { echo "Khong cai duoc PyInstaller"; exit 1; }
    note "KHONG cai duoc $pkg : chuc nang tuong ung se thieu."; fi
done

step "2/7  Model tieng Viet/Latin cua RapidOCR"
(cd "$ROOT" && "$VPY" -c "from litepdf import ocr; ocr.rapid_engine('latin', ''); print('ok')") \
  && note "model latin: OK" || note "Chua tai duoc model latin: app se tu tai o lan dung dau."

step "3/7  Du lieu ngon ngu Tesseract (vie, eng, osd)"
mkdir -p "$VENDOR/tessdata"
for l in vie eng osd; do
  f="$VENDOR/tessdata/$l.traineddata"
  [ -s "$f" ] || curl -L --fail -sS --retry 3 -o "$f" "https://github.com/tesseract-ocr/tessdata_fast/raw/main/$l.traineddata"
done

step "4/7  Dong goi app (.app) bang PyInstaller"
ICONSET="$WORK/app.iconset"; rm -rf "$ICONSET"; mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z $s $s "$ROOT/assets/app_icon_1024.png" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  sips -z $((s*2)) $((s*2)) "$ROOT/assets/app_icon_1024.png" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$WORK/app.icns"
rm -rf "$WORK/dist"
LITEPDF_TESSDATA="$VENDOR/tessdata" LITEPDF_ICNS="$WORK/app.icns" LITEPDF_BUILD="$BUILD" \
  "$VPY" -m PyInstaller "$ROOT/packaging/PDFEditorLite.spec" --noconfirm --distpath "$WORK/dist" --workpath "$WORK/pyi" \
  >> "$WORK/pyinstaller.log" 2>&1 || { tail -40 "$WORK/pyinstaller.log" | tee -a "$LOG"; exit 1; }
APP="$WORK/dist/PDF Editor Lite.app"
[ -x "$APP/Contents/MacOS/PDFEditorLite" ] || { echo "PyInstaller that bai"; exit 1; }
codesign --force --deep -s - "$APP" >> "$LOG" 2>&1 || note "canh bao: ky ad-hoc khong thanh cong"
{ echo "--- cv2 trong goi:"; ls -la "$APP/Contents/Frameworks/cv2" "$APP/Contents/Resources/cv2" 2>&1 | head -60; } >> "$LOG"
note "dung luong .app: $(du -sm "$APP" | cut -f1) MB"

step "5/7  Tu kiem tra ban dong goi"
ST="$WORK/selftest.json"; rm -f "$ST"
"$APP/Contents/MacOS/PDFEditorLite" --selftest "$ST" & SP=$!
( sleep 300; kill $SP 2>/dev/null ) & WD=$!
wait $SP 2>/dev/null || true; kill $WD 2>/dev/null || true
[ -s "$ST" ] || { note "thu lai tu kiem tra o che do khong man hinh"; QT_QPA_PLATFORM=offscreen "$APP/Contents/MacOS/PDFEditorLite" --selftest "$ST" || true; }
[ -s "$ST" ] || { echo "Ban dong goi khong chay duoc (khong co selftest.json)" | tee -a "$LOG"; exit 1; }
cat "$ST"; cat "$ST" >> "$LOG"
if grep -Eq '"(pymupdf|pyhanko|fonts)": "LOI' "$ST"; then echo "Thieu thanh phan bat buoc"; exit 1; fi

step "6/7  LibreOffice"
PK="$WORK/pkgs"; rm -rf "$PK" "$WORK/scripts_lo" "$WORK/scripts_ai" "$WORK/root"; mkdir -p "$PK" "$WORK/root"
WITH_LO=0
if [ -z "${NO_LIBREOFFICE:-}" ]; then
  LO="$VENDOR/LibreOffice.dmg"
  if [ ! -s "$LO" ]; then
    IDX="$(curl -L --fail -sS --max-time 120 https://download.documentfoundation.org/libreoffice/stable/)"
    V="$(echo "$IDX" | grep -oE 'href="[0-9]+\.[0-9]+\.[0-9]+/"' | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | sort -t. -k1,1n -k2,2n -k3,3n | head -1)"
    [ -n "$V" ] || { echo "Khong doc duoc danh sach phien ban LibreOffice"; exit 1; }
    note "LibreOffice phien ban $V ($LOARCH)"
    curl -L --fail -sS --retry 3 --max-time 1500 -o "$LO.part" \
      "https://download.documentfoundation.org/libreoffice/stable/$V/mac/$LOARCH/LibreOffice_${V}_MacOS_${LOFILE}.dmg"
    mv "$LO.part" "$LO"
  fi
  note "LibreOffice.dmg: $(du -m "$LO" | cut -f1) MB"
  mkdir -p "$WORK/scripts_lo"; cp "$LO" "$WORK/scripts_lo/LibreOffice.dmg"
  install -m 755 "$ROOT/packaging/macos/postinstall_lo.sh" "$WORK/scripts_lo/postinstall"
  pkgbuild --nopayload --scripts "$WORK/scripts_lo" --identifier dev.ngthhung.pdfeditorlite.libreoffice --version "$VER" "$PK/lo.pkg" >> "$LOG" 2>&1
  WITH_LO=1
fi
mkdir -p "$WORK/scripts_ai"
sed "s/@MODEL@/$MODEL/g" "$ROOT/packaging/macos/postinstall_ai.sh" > "$WORK/scripts_ai/postinstall"; chmod 755 "$WORK/scripts_ai/postinstall"
pkgbuild --nopayload --scripts "$WORK/scripts_ai" --identifier dev.ngthhung.pdfeditorlite.ollama --version "$VER" "$PK/ai.pkg" >> "$LOG" 2>&1

step "7/7  Tao bo cai .pkg"
ditto "$APP" "$WORK/root/PDF Editor Lite.app"
pkgbuild --analyze --root "$WORK/root" "$WORK/comp.plist" >> "$LOG" 2>&1
/usr/libexec/PlistBuddy -c "Set :0:BundleIsRelocatable false" "$WORK/comp.plist"      # luon cai vao /Applications
pkgbuild --root "$WORK/root" --component-plist "$WORK/comp.plist" --install-location /Applications \
  --identifier dev.ngthhung.pdfeditorlite.app --version "$VER" "$PK/app.pkg" >> "$LOG" 2>&1
LOLINE=""; LOCHOICE=""
if [ "$WITH_LO" = 1 ]; then
  LOLINE='<line choice="lo"/>'
  LOCHOICE='<choice id="lo" title="LibreOffice: chuyển Word / Excel / PowerPoint sang PDF" description="Kèm sẵn trong bộ cài. Bỏ qua nếu máy đã có LibreOffice." selected="true"><pkg-ref id="dev.ngthhung.pdfeditorlite.libreoffice"/></choice><pkg-ref id="dev.ngthhung.pdfeditorlite.libreoffice" version="'$VER'" onConclusion="none">lo.pkg</pkg-ref>'
fi
RES="$WORK/res"; rm -rf "$RES"; mkdir -p "$RES"; cp "$ROOT/packaging/macos/welcome.html" "$RES/"
cat > "$WORK/distribution.xml" <<XML
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
  <title>PDF Editor Lite $VER</title>
  <welcome file="welcome.html" mime-type="text/html"/>
  <options customize="always" require-scripts="false" hostArchitectures="$HOSTS"/>
  <domains enable_localSystem="true"/>
  <os-version min="12.0"/>
  <choices-outline>
    <line choice="app"/>
    $LOLINE
    <line choice="ai"/>
  </choices-outline>
  <choice id="app" title="PDF Editor Lite" description="Ứng dụng chính: xem, sửa, ghép/tách, in, bookmark, ký số, chuyển đổi, dịch, so sánh. Kèm sẵn OCR Tesseract (tiếng Việt, tiếng Anh), RapidOCR và hướng dẫn sử dụng." enabled="false" selected="true"><pkg-ref id="dev.ngthhung.pdfeditorlite.app"/></choice>
  <pkg-ref id="dev.ngthhung.pdfeditorlite.app" version="$VER" onConclusion="none">app.pkg</pkg-ref>
  $LOCHOICE
  <choice id="ai" title="AI dịch chạy ngay trên máy (Ollama + model $MODEL)" description="Không cần API key. TẢI VỀ khi cài: Ollama và model dịch, tổng cộng vài GB, cần mạng và máy có RAM từ 8 GB. Có thể mất khá lâu." start_selected="false"><pkg-ref id="dev.ngthhung.pdfeditorlite.ollama"/></choice>
  <pkg-ref id="dev.ngthhung.pdfeditorlite.ollama" version="$VER" onConclusion="none">ai.pkg</pkg-ref>
</installer-gui-script>
XML
PKG="$OUT/PDF-Editor-Lite-${VER}-build${BUILD}-macOS-${TAG}.pkg"
productbuild --distribution "$WORK/distribution.xml" --package-path "$PK" --resources "$RES" "$PKG" >> "$LOG" 2>&1
note "XONG: $(basename "$PKG")  $(du -m "$PKG" | cut -f1) MB"
echo; echo "XONG. File cai: $PKG"
