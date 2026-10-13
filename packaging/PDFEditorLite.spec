# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: đóng gói PDF Editor Lite thành thư mục chạy độc lập (onedir). Dùng chung cho Windows / macOS / Linux.
#   pyinstaller packaging/PDFEditorLite.spec --noconfirm
import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
datas, binaries, hidden = [], [], []


def take(pkg, required=True):
    try:
        d, b, h = collect_all(pkg)
    except Exception:
        if required:
            raise
        return
    datas.extend(d)
    binaries.extend(b)
    hidden.extend(h)


for pkg in ("pymupdf", "pymupdf_fonts", "pyhanko", "pyhanko_certvalidator", "asn1crypto", "tzlocal", "fontTools"):
    take(pkg, required=pkg in ("pymupdf", "pyhanko"))
for pkg in ("rapidocr", "onnxruntime", "pdf2docx", "pkcs11", "docx", "cv2", "omegaconf", "pyclipper", "shapely"):
    if pkg == "cv2" and sys.platform == "darwin":
        continue                       # macOS: để hook chuẩn của PyInstaller lo OpenCV (gom tay làm hỏng bộ nạp của cv2 trong .app)
    take(pkg, required=False)          # phần mở rộng: thiếu thì app vẫn chạy, chỉ thiếu đúng chức năng đó
hidden += collect_submodules("litepdf")
datas += [(os.path.join(ROOT, "assets"), "assets")]

tess = os.environ.get("LITEPDF_TESSDATA")      # macOS / Linux: dữ liệu Tesseract nằm luôn trong bản đóng gói
if tess and os.path.isdir(tess):
    datas += [(tess, os.path.join("resources", "tessdata"))]

icon = os.path.join(ROOT, "assets", "app_icon.ico") if sys.platform.startswith("win") else os.environ.get("LITEPDF_ICNS")

def _version_file():
    """Thông tin phiên bản của PDFEditorLite.exe (Properties → Details), điền số build vào."""
    src = open(os.path.join(SPECPATH, "windows", "version_info.txt"), encoding="utf-8").read()
    build = "".join(ch for ch in os.environ.get("LITEPDF_BUILD", "0") if ch.isdigit()) or "0"
    out = os.path.join(os.path.abspath(os.path.join(SPECPATH, "..", "build_win")), "version_info.txt")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(src.replace("@B@", build).replace("\\u00a9", "\u00a9"))
    return out


a = Analysis([os.path.join(ROOT, "main.py")], pathex=[ROOT], binaries=binaries, datas=datas, hiddenimports=hidden,
             excludes=["tkinter", "matplotlib", "IPython", "pytest", "PyQt5", "PyQt6", "PySide2", "torch", "paddle"],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="PDFEditorLite", console=False, icon=icon,
          version=_version_file() if sys.platform.startswith("win") else None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="PDFEditorLite")

if sys.platform == "darwin":
    app = BUNDLE(coll, name="PDF Editor Lite.app", icon=icon, bundle_identifier="dev.ngthhung.pdfeditorlite", version="1.0.0",
                 info_plist={
                     "CFBundleDisplayName": "PDF Editor Lite", "CFBundleName": "PDF Editor Lite",
                     "CFBundleShortVersionString": "1.0.0", "CFBundleVersion": os.environ.get("LITEPDF_BUILD", "1"),
                     "NSHighResolutionCapable": True, "LSMinimumSystemVersion": "12.0",
                     "NSHumanReadableCopyright": "Copyright \u00a9 2026 ngthhung",
                     "CFBundleGetInfoString": "PDF Editor Lite 1.0.0 by ngthhung",
                     "CFBundleDocumentTypes": [{
                         "CFBundleTypeName": "PDF", "CFBundleTypeRole": "Editor", "LSHandlerRank": "Alternate",
                         "LSItemContentTypes": ["com.adobe.pdf"], "CFBundleTypeExtensions": ["pdf"]}],
                 })
