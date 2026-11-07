"""Ký số PDF (file .pfx/.p12, USB token PKCS#11) và kiểm tra chữ ký."""
from __future__ import annotations

import glob
import io
import logging
import os
import sys
import tempfile
import uuid
from datetime import datetime

import pymupdf

from . import tools


for _n in ('pyhanko', 'pyhanko_certvalidator', 'pyhanko.sign'):
    logging.getLogger(_n).setLevel(logging.CRITICAL)
    logging.getLogger(_n).propagate = False


class SignError(Exception):
    pass


# ------------------------------------------------------------ thông tin chứng thư
def cert_info(cert) -> dict:
    """cert: asn1crypto.x509.Certificate"""
    subj = cert.subject.native
    iss = cert.issuer.native

    def first(d, *keys):
        for k in keys:
            v = d.get(k)
            if v:
                return v if isinstance(v, str) else ", ".join(map(str, v))
        return ""

    return {
        "cn": first(subj, "common_name", "organization_name") or cert.subject.human_friendly,
        "org": first(subj, "organization_name"),
        "uid": first(subj, "user_id", "0.9.2342.19200300.100.1.1", "serial_number"),
        "issuer": first(iss, "common_name", "organization_name") or cert.issuer.human_friendly,
        "serial": format(cert.serial_number, "X"),
        "not_before": cert.not_valid_before,
        "not_after": cert.not_valid_after,
        "expired": cert.not_valid_after < datetime.now(cert.not_valid_after.tzinfo),
    }


# ------------------------------------------------------------------ file PFX
def load_pfx(path: str, password: str):
    from pyhanko.sign import signers
    try:
        s = signers.SimpleSigner.load_pkcs12(path, passphrase=password.encode("utf-8") if password else None)
    except Exception as e:
        raise SignError(f"Không đọc được chứng thư: {e}")
    if s is None or s.signing_cert is None:
        raise SignError("Sai mật khẩu hoặc file chứng thư không hợp lệ.")
    return s


# --------------------------------------------------------------- USB token
_KNOWN_LIBS = [
    "vnpt-ca_csp11.dll", "vnptca_p11_v6.dll", "vnpt-ca_v34.dll", "viettel-ca_v5.dll", "viettel-ca_v6.dll",
    "viettel-ca_v4.dll", "fpt-ca.dll", "fpt-ca-stx.dll", "BkavCA.dll", "BkavCAv2S.dll", "bkavcaetoken.dll",
    "nca_v6.dll", "nca_v4.dll", "newtel-ca.dll", "cmc-ca_v6.dll", "ca2_csp11.dll", "ca2_v6.dll",
    "vdctdcsp11.dll", "st3csp11.dll", "safe-ca.dll", "smartsign.dll", "efy-ca_v6.dll", "easyca_v6.dll",
    "misa-ca_v6.dll", "eps2003csp11.dll", "eps2003csp11v2.dll", "ShuttleCsp11_3003.dll", "ngp11v211.dll",
    "eTPKCS11.dll", "wdpkcs.dll", "gclib.dll", "cryptoki.dll", "opensc-pkcs11.dll",
]
_PATTERNS = ["*csp11*.dll", "*pkcs11*.dll", "*p11*.dll", "*-ca*.dll", "*_ca_*.dll", "*ca_v*.dll"]


def find_pkcs11_libs() -> list[str]:
    """Dò thư viện PKCS#11 của USB token đã cài trên máy (trình điều khiển token)."""
    found: list[str] = []
    if sys.platform.startswith("win"):
        win = os.environ.get("WINDIR", r"C:\Windows")
        dirs = [os.path.join(win, "System32"), os.path.join(win, "SysWOW64")]
        is64 = sys.maxsize > 2 ** 32
        dirs = dirs[:1] if is64 else dirs[::-1]
        for d in dirs:
            for n in _KNOWN_LIBS:
                p = os.path.join(d, n)
                if os.path.exists(p):
                    found.append(p)
            for pat in _PATTERNS:
                found += glob.glob(os.path.join(d, pat))
    elif sys.platform == "darwin":
        for pat in ["/usr/local/lib/*pkcs11*.dylib", "/usr/local/lib/*-ca*.dylib", "/Library/OpenSC/lib/*pkcs11*.so",
                    "/usr/local/lib/libeToken.dylib", "/usr/local/lib/libcastle*.dylib",
                    "/Library/Frameworks/*.framework/*pkcs11*", "/opt/homebrew/lib/*pkcs11*.so",
                    "/opt/homebrew/lib/softhsm/*.so"]:
            found += glob.glob(pat)
    else:
        for pat in ["/usr/lib/*pkcs11*.so", "/usr/lib/*-ca*.so", "/usr/lib/*/opensc-pkcs11.so",
                    "/usr/lib/*/pkcs11/*.so", "/usr/lib/libeToken.so*", "/usr/lib/*csp11*.so", "/opt/*/lib/*pkcs11*.so",
                    "/usr/lib/softhsm/*.so", "/usr/lib/*/softhsm/*.so", "/usr/local/lib/*pkcs11*.so",
                    "/usr/local/lib/softhsm/*.so", "/usr/lib/*/libcastle*.so*"]:
            found += glob.glob(pat)
    seen, out = set(), []
    for p in found:
        k = os.path.normcase(os.path.realpath(p))
        base = os.path.basename(p).lower()
        if k in seen or base.startswith(("p11-kit", "libp11-kit", "msp", "wp", "msvc", "vcamp", "vcomp", "microsoft-",
                                         "api-ms-", "ucrt")):
            continue
        seen.add(k)
        # tên có hãng chữ ký số (viettel, vnpt, safe…) thì giữ luôn (driver nén không đọc được tên hàm trong file)
        if any(key in base for key, _ in _VENDORS) or "safe" in base or _is_pkcs11(p):
            out.append(p)
    return out


def _is_pkcs11(path: str) -> bool:
    """File thư viện có hàm C_GetFunctionList (mọi driver PKCS#11 đều phải có): loại các file trùng mẫu tên nhưng không
    phải driver token (vd. msvcp110.dll khớp mẫu *p11*)."""
    try:
        if os.path.getsize(path) > 64 * 1024 * 1024:
            return True
        with open(path, "rb") as f:
            return b"C_GetFunctionList" in f.read()
    except OSError:
        return False


def probe_main(lib_path: str, out_path: str) -> int:
    """Chạy trong tiến trình phụ (PDFEditorLite --probe-pkcs11 <driver> <file kết quả>): nạp thử một driver và ghi ra
    các token đang cắm mà driver đó nhận được. Mỗi tiến trình chỉ nạp được một driver nên mỗi driver thử riêng."""
    import json
    res: dict = {"lib": lib_path, "tokens": [], "error": ""}
    try:
        import pkcs11
        lib = pkcs11.lib(lib_path)
        for slot in lib.get_slots(token_present=True):
            try:
                t = slot.get_token()
                ser = t.serial
                ser = ser.decode(errors="ignore") if isinstance(ser, bytes) else str(ser or "")
                res["tokens"].append({"slot": int(slot.slot_id), "label": (t.label or "").strip(), "serial": ser.strip(),
                                      "manufacturer": (getattr(t, "manufacturer_id", "") or "").strip(),
                                      "model": (getattr(t, "model", "") or "").strip(),
                                      "slot_desc": (getattr(slot, "slot_description", "") or "").strip()})
            except Exception:
                continue
    except Exception as e:
        res["error"] = f"{type(e).__name__}: {e}"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False)
    return 0


def _probe_cmd() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable]
    main = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
    return [sys.executable, main]


_VENDORS = [("viettel", "Viettel-CA"), ("vnpt", "VNPT-CA"), ("fpt", "FPT-CA"), ("bkav", "BKAV-CA"), ("nca", "NC-CA"),
            ("newtel", "Newtel-CA"), ("cmc", "CMC-CA"), ("ca2", "CA2"), ("safe", "Safe-CA"), ("smartsign", "SmartSign"),
            ("efy", "EFY-CA"), ("easyca", "EasyCA"), ("misa", "MISA-CA"), ("eps2003", "ePass2003"),
            ("shuttle", "Shuttle"), ("etpkcs11", "SafeNet eToken"), ("opensc", "OpenSC"), ("softhsm", "SoftHSM")]


def vendor_of(lib_path: str, token: dict | None = None) -> str:
    """Tên nhà cung cấp dễ hiểu, đoán từ tên file driver (và thông tin token)."""
    text = (os.path.basename(lib_path) + " " + " ".join(str(v) for v in (token or {}).values())).lower()
    for key, name in _VENDORS:
        if key in text:
            return name
    return os.path.splitext(os.path.basename(lib_path))[0]


def probe_tokens(libs: list[str] | None = None, timeout: float = 20.0) -> list[dict]:
    """Dò token đang cắm: thử từng driver đã cài (song song, mỗi driver một tiến trình phụ). Trả về danh sách
    {lib, vendor, slot, label, serial, manufacturer, model}; một token được nhiều driver nhận thì chỉ giữ một dòng,
    ưu tiên driver đúng hãng của token."""
    import json
    import subprocess
    import threading
    libs = find_pkcs11_libs() if libs is None else libs
    found: list[dict] = []
    lock = threading.Lock()
    tmp = tempfile.mkdtemp(prefix="litepdf-p11-")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def one(lib: str, k: int):
        out = os.path.join(tmp, f"{k}.json")
        try:
            subprocess.run(_probe_cmd() + ["--probe-pkcs11", lib, out], timeout=timeout, capture_output=True,
                           creationflags=flags)
            data = json.load(open(out, encoding="utf-8"))
        except Exception:
            return
        with lock:
            for t in data.get("tokens", []):
                found.append(dict(t, lib=lib, vendor=vendor_of(lib, t)))
    threads = []
    for k, lib in enumerate(libs):
        th = threading.Thread(target=one, args=(lib, k), daemon=True)
        th.start()
        threads.append(th)
        if len([t for t in threads if t.is_alive()]) >= 6:       # không chạy quá nhiều tiến trình cùng lúc
            for t in threads:
                t.join(timeout)
    for th in threads:
        th.join(timeout + 5)
    try:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    except Exception:
        pass
    return dedupe_tokens(found)


def dedupe_tokens(found: list[dict]) -> list[dict]:
    """Một token (cùng số serial) được nhiều driver nhận: giữ driver mà tên hãng khớp với thông tin token."""
    best: dict = {}
    for t in found:
        key = (t["serial"] or t["label"] or t["lib"]).lower()
        info = " ".join([t["label"], t["manufacturer"], t["model"], t.get("slot_desc", "")]).lower()
        lib_l = os.path.basename(t["lib"]).lower()
        score = 2 if any(k in lib_l and k in info for k, _ in _VENDORS) else (1 if t["label"] else 0)
        if key not in best or score > best[key][0]:
            best[key] = (score, t)
    return sorted((v[1] for v in best.values()), key=lambda t: (t["vendor"], t["label"]))


_LIB_CACHE: dict[str, object] = {}


def _lib(path: str):
    import pkcs11
    key = os.path.normcase(os.path.abspath(path))
    if key not in _LIB_CACHE:
        if _LIB_CACHE:
            raise SignError("Mỗi lần chạy chỉ dùng được một trình điều khiển token. "
                            "Hãy đóng PDF Editor Lite rồi mở lại để đổi sang token khác.")
        try:
            _LIB_CACHE[key] = pkcs11.lib(path)
        except Exception as e:
            raise SignError(f"Không nạp được trình điều khiển token:\n{path}\n{e}")
    return _LIB_CACHE[key]


def list_tokens(lib_path: str) -> list[dict]:
    lib = _lib(lib_path)
    out = []
    try:
        for slot in lib.get_slots(token_present=True):
            try:
                t = slot.get_token()
                out.append({"slot": slot.slot_id, "label": (t.label or "").strip(),
                            "serial": (t.serial or b"").decode(errors="ignore") if isinstance(t.serial, bytes)
                            else str(t.serial or ""), "token": t})
            except Exception:
                continue
    except Exception as e:
        raise SignError(f"Không đọc được danh sách token: {e}")
    return out


class TokenSession:
    """Phiên làm việc với USB token sau khi nhập PIN."""

    def __init__(self, lib_path: str, token: dict, pin: str):
        import pkcs11
        try:
            self.session = token["token"].open(user_pin=pin)
        except pkcs11.exceptions.PinIncorrect:
            raise SignError("Sai mã PIN. Lưu ý: nhập sai nhiều lần token sẽ bị khoá.")
        except pkcs11.exceptions.PinLocked:
            raise SignError("Token đã bị khoá PIN. Liên hệ nhà cung cấp chữ ký số để mở khoá.")
        except Exception as e:
            raise SignError(f"Không đăng nhập được token: {type(e).__name__} {e}")

    def certificates(self) -> list[dict]:
        from asn1crypto import x509
        from pkcs11 import Attribute, ObjectClass
        keys = set()
        try:
            for k in self.session.get_objects({Attribute.CLASS: ObjectClass.PRIVATE_KEY}):
                try:
                    keys.add(bytes(k[Attribute.ID]))
                except Exception:
                    pass
        except Exception:
            pass
        out = []
        for o in self.session.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE}):
            try:
                cert = x509.Certificate.load(bytes(o[Attribute.VALUE]))
                cid = bytes(o[Attribute.ID])
                try:
                    label = o[Attribute.LABEL]
                except Exception:
                    label = ""
            except Exception:
                continue
            if keys and cid not in keys:
                continue  # chứng thư CA trung gian, không có khoá riêng
            out.append({"id": cid, "label": label, "cert": cert, "info": cert_info(cert)})
        return out

    def signer(self, entry: dict):
        from pyhanko.sign.pkcs11 import PKCS11Signer
        return PKCS11Signer(self.session, signing_cert=entry["cert"], cert_id=entry["id"], key_id=entry["id"],
                            other_certs_to_pull=None)

    def close(self):
        try:
            self.session.close()
        except Exception:
            pass


# ----------------------------------------------------------- khung chữ ký hiển thị
# Các dòng thông tin có thể hiện trong khung chữ ký: (mã, nhãn mặc định). "custom" là dòng chữ tự nhập.
SIGN_FIELDS = [("name", "Ký bởi"), ("org", "Đơn vị"), ("uid", "Mã số"), ("time", "Ngày ký"), ("reason", "Lý do"),
               ("location", "Nơi ký"), ("issuer", "Cấp bởi"), ("custom", "")]
SIGN_FIELD_NAMES = {"name": "Người ký", "org": "Đơn vị", "uid": "Mã số (MST / CCCD)", "time": "Thời gian ký",
                    "reason": "Lý do ký", "location": "Nơi ký", "issuer": "Nhà cung cấp chứng thư", "custom": "Dòng tự nhập"}
DEFAULT_SIGN_LAYOUT = [{"key": k, "label": lb, "on": k in ("name", "org", "time")} for k, lb in SIGN_FIELDS]


def normalize_layout(items) -> list[dict]:
    """Bố trí dòng đã lưu (có thể từ bản cũ, thiếu dòng mới) -> danh sách đủ mọi dòng, giữ thứ tự người dùng đã chọn."""
    out, seen = [], set()
    for it in items or []:
        if isinstance(it, dict) and it.get("key") in dict(SIGN_FIELDS) and it["key"] not in seen:
            seen.add(it["key"])
            out.append({"key": it["key"], "label": str(it.get("label", dict(SIGN_FIELDS)[it["key"]])),
                        "on": bool(it.get("on")), **({"text": str(it.get("text", ""))} if it["key"] == "custom" else {})})
    for k, lb in SIGN_FIELDS:
        if k not in seen:
            out.append({"key": k, "label": lb, "on": False, **({"text": ""} if k == "custom" else {})})
    return out


def sign_lines(layout: list[dict], values: dict) -> list[str]:
    """Các dòng chữ của khung chữ ký theo bố trí: 'Nhãn: giá trị' (nhãn để trống thì chỉ có giá trị).
    Dòng không có giá trị (vd. chứng thư không ghi đơn vị) thì bỏ qua."""
    out = []
    for it in normalize_layout(layout):
        if not it["on"]:
            continue
        val = (it.get("text") if it["key"] == "custom" else values.get(it["key"])) or ""
        val = str(val).strip()
        if it["key"] == "org" and val and val == str(values.get("name", "")).strip():
            continue                             # đơn vị trùng tên người ký (chứng thư tổ chức): không lặp lại
        if not val:
            continue
        label = it["label"].strip()
        out.append(f"{label}: {val}" if label and it["key"] != "custom" else (f"{label} {val}".strip() if label else val))
    return out


def _image_size(path: str) -> tuple[int, int] | None:
    try:
        pix = pymupdf.Pixmap(path)
        return pix.width, pix.height
    except Exception:
        return None


def _fit(box: pymupdf.Rect, size: tuple[int, int] | None) -> pymupdf.Rect:
    """Khung ảnh giữ đúng tỉ lệ ảnh, nằm giữa `box`."""
    if not size or not size[0] or not size[1] or box.is_empty:
        return pymupdf.Rect(box)
    k = min(box.width / size[0], box.height / size[1])
    w, h = size[0] * k, size[1] * k
    c = (box.tl + box.br) / 2
    return pymupdf.Rect(c.x - w / 2, c.y - h / 2, c.x + w / 2, c.y + h / 2)


def appearance_boxes(width: float, height: float, has_lines: bool, image_path: str | None, image_pos: str = "auto",
                     image_rect=None, text_rect=None) -> tuple[pymupdf.Rect | None, pymupdf.Rect]:
    """(khung ảnh thật sự được vẽ — đúng tỉ lệ ảnh, khung chữ) trong khung chữ ký width × height.
    image_pos 'custom': ảnh ở `image_rect` (tỉ lệ 0..1 theo khung chữ ký, người dùng kéo trong khung xem trước),
    'behind': ảnh phủ giữa cả khung; hai kiểu này chữ chiếm cả khung và nằm đè lên ảnh.
    text_rect (tỉ lệ 0..1): vùng chữ người dùng tự kéo; None thì vùng chữ tính theo vị trí ảnh."""
    img, txt = _appearance_boxes(width, height, has_lines, image_path, image_pos, image_rect)
    if text_rect and len(text_rect) == 4:
        x0, y0, x1, y1 = (float(v) for v in text_rect)
        box = pymupdf.Rect(x0 * width, y0 * height, x1 * width, y1 * height)
        if box.width >= 6 and box.height >= 4:
            txt = box
    return img, txt


def _appearance_boxes(width: float, height: float, has_lines: bool, image_path: str | None, image_pos: str = "auto",
                      image_rect=None) -> tuple[pymupdf.Rect | None, pymupdf.Rect]:
    pad = 3
    r = pymupdf.Rect(0, 0, width, height)
    text_rect = r + (pad, pad, -pad, -pad)
    if not image_path or not os.path.exists(image_path):
        return None, text_rect
    size = _image_size(image_path)
    if image_pos == "custom" and image_rect and len(image_rect) == 4:
        x0, y0, x1, y1 = (float(v) for v in image_rect)
        box = pymupdf.Rect(x0 * width, y0 * height, x1 * width, y1 * height)
        return _fit(box if not box.is_empty else text_rect, size), text_rect    # khung khác tỉ lệ: ảnh không bị méo
    if image_pos == "behind" or not has_lines:
        return _fit(text_rect, size), text_rect
    pos = image_pos if image_pos in ("left", "right", "top", "bottom") else ("left" if width >= height * 1.6 else "top")
    if pos == "left":
        img = pymupdf.Rect(pad, pad, width * 0.4, height - pad)
        text_rect = pymupdf.Rect(width * 0.4 + pad, pad, width - pad, height - pad)
    elif pos == "right":
        img = pymupdf.Rect(width * 0.6, pad, width - pad, height - pad)
        text_rect = pymupdf.Rect(pad, pad, width * 0.6 - pad, height - pad)
    elif pos == "top":
        img = pymupdf.Rect(pad, pad, width - pad, height * 0.5)
        text_rect = pymupdf.Rect(pad, height * 0.5, width - pad, height - pad)
    else:
        img = pymupdf.Rect(pad, height * 0.5, width - pad, height - pad)
        text_rect = pymupdf.Rect(pad, pad, width - pad, height * 0.5)
    return _fit(img, size), text_rect


def make_appearance(width: float, height: float, lines: list[str], image_path: str | None = None,
                    border: bool = True, color=(0.75, 0.05, 0.05), image_pos: str = "auto", align: str = "left",
                    font_size: float | None = None, bold_first: bool = False, image_rect=None,
                    text_rect=None) -> bytes:
    """Dựng hình khung chữ ký (PDF 1 trang) gồm ảnh chữ ký và các dòng thông tin.
    image_pos: 'auto' | 'left' | 'right' | 'top' | 'bottom' | 'behind' (ảnh nằm dưới chữ) | 'custom' (ảnh ở
    image_rect = (x0, y0, x1, y1) tỉ lệ 0..1 theo khung); align: 'left' | 'center' | 'right';
    font_size: None = tự chọn cỡ lớn nhất vừa khung, số = cỡ cố định (vẫn tự thu nhỏ nếu không vừa)."""
    doc = pymupdf.open()
    page = doc.new_page(width=width, height=height)
    r = page.rect
    if border:
        page.draw_rect(r + (0.6, 0.6, -0.6, -0.6), color=color, width=1.0)
    img_rect, text_rect = appearance_boxes(width, height, bool(lines), image_path, image_pos, image_rect, text_rect)
    if img_rect is not None:                     # vẽ ảnh trước: chữ (nếu chồng lên) nằm đè trên ảnh
        try:
            page.insert_image(img_rect, filename=image_path, keep_proportion=False)
        except Exception:
            pass
    if lines:
        text = "\n".join(lines)
        font = tools.pick_font("arial", 0, text)
        bold = tools.pick_font("arial", 16, lines[0], bold=True) if bold_first else None
        al = {"center": 1, "right": 2}.get(align, 0)
        size = float(font_size) if font_size else 11.0
        while size > 3.5:
            tw = pymupdf.TextWriter(r, color=color)
            try:
                if bold is not None:             # dòng đầu (thường là tên người ký) in đậm
                    left = tw.fill_textbox(text_rect, lines[0], font=bold, fontsize=size, lineheight=1.15, align=al)
                    if not left and len(lines) > 1:
                        y = tw.last_point.y if tw.last_point else text_rect.y0
                        rest = pymupdf.Rect(text_rect.x0, y + 0.3 * size, text_rect.x1, text_rect.y1)
                        left = ["x"] if rest.is_empty else tw.fill_textbox(rest, "\n".join(lines[1:]), font=font,
                                                                           fontsize=size, lineheight=1.15, align=al)
                else:
                    left = tw.fill_textbox(text_rect, text, font=font, fontsize=size, lineheight=1.15, align=al)
            except Exception:
                left = ["x"]
            if not left:
                tw.write_text(page)
                break
            size -= 0.5
    data = doc.tobytes(deflate=True)
    doc.close()
    return data


def pdf_box(page, rect) -> tuple[float, float, float, float]:
    """Đổi khung trên trang (toạ độ PyMuPDF) sang toạ độ PDF chuẩn cho ô chữ ký."""
    r = pymupdf.Rect(rect) * page.transformation_matrix  # rect: toạ độ trang chưa xoay
    r.normalize()
    return (round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2))


def empty_signature_fields(data: bytes) -> list[str]:
    try:
        from pyhanko.pdf_utils.reader import PdfFileReader
        from pyhanko.sign.fields import enumerate_sig_fields
        r = PdfFileReader(io.BytesIO(data), strict=False)
        return [name for name, _v, _ref in enumerate_sig_fields(r, filled_status=False)]
    except Exception:
        return []


def sign_pdf(data: bytes, signer, *, page_index: int | None = None, box=None, appearance: bytes | None = None,
             existing_field: str | None = None, reason: str = "", location: str = "", contact: str = "",
             tsa_url: str = "", certify: bool = False) -> bytes:
    """Ký số và trả về bytes PDF đã ký (ghi nối tiếp, không phá chữ ký có sẵn)."""
    from pyhanko import stamp
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import fields, signers

    try:
        w = IncrementalPdfFileWriter(io.BytesIO(data), strict=False)
    except Exception as e:
        raise SignError(f"Không đọc được PDF để ký: {e}")
    name = existing_field or ("ChuKy_" + uuid.uuid4().hex[:8])
    meta = signers.PdfSignatureMetadata(
        field_name=name, md_algorithm="sha256", reason=reason or None, location=location or None,
        contact_info=contact or None, certify=certify,
        docmdp_permissions=fields.MDPPerm.FILL_FORMS)
    spec = None
    if not existing_field:
        if box is not None and page_index is not None:
            spec = fields.SigFieldSpec(sig_field_name=name, on_page=page_index, box=tuple(box))
        else:
            spec = fields.SigFieldSpec(sig_field_name=name)  # chữ ký ẩn
    timestamper = None
    if tsa_url:
        try:
            from pyhanko.sign import timestamps
            timestamper = timestamps.HTTPTimeStamper(tsa_url)
        except Exception as e:
            raise SignError(f"Không dùng được máy chủ dấu thời gian: {e}")
    style = None
    tmp = None
    if appearance and (existing_field or box is not None):
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.write(appearance)
        tmp.close()
        style = stamp.StaticStampStyle.from_pdf_file(tmp.name, border_width=0, background_opacity=1)
    try:
        ps = signers.PdfSigner(meta, signer=signer, timestamper=timestamper, stamp_style=style,
                               new_field_spec=spec)
        out = io.BytesIO()
        ps.sign_pdf(w, output=out)
        return out.getvalue()
    except SignError:
        raise
    except Exception as e:
        removed = tools.exe_removed_message(e)
        if removed:
            raise SignError("Ký số thất bại.\n\n" + removed)
        msg = f"{type(e).__name__}: {e}"
        if tsa_url and ("imestamp" in msg or "Connection" in msg or "HTTP" in msg):
            msg = "Không kết nối được máy chủ dấu thời gian (TSA). Bỏ trống ô TSA để ký không dấu thời gian.\n" + msg
        raise SignError("Ký số thất bại.\n" + msg)
    finally:
        if tmp:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass


# ------------------------------------------------------------ kiểm tra chữ ký
def _load_certs(raw: bytes) -> list:
    from asn1crypto import pem, x509
    out = []
    try:
        if pem.detect(raw):
            for _t, _h, der in pem.unarmor(raw, multiple=True):
                out.append(x509.Certificate.load(der))
        else:
            out.append(x509.Certificate.load(raw))
    except Exception:
        pass
    return out


def _load_trust(trust_dir: str | None) -> list:
    roots = []
    if trust_dir and os.path.isdir(trust_dir):
        for f in os.listdir(trust_dir):
            if not f.lower().endswith((".cer", ".crt", ".pem", ".der")):
                continue
            try:
                roots += _load_certs(open(os.path.join(trust_dir, f), "rb").read())
            except Exception:
                continue
    return roots


_SYSTEM_CERTS: dict = {}


def system_certs() -> tuple[list, list]:
    """(chứng thư gốc tin cậy, chứng thư trung gian) có sẵn trong máy.
    Windows: kho "Trusted Root" và "Intermediate CA" của Windows — cài driver USB token (Viettel-CA, VNPT-CA, FPT-CA…)
    thường đã cài sẵn chứng thư gốc quốc gia (MIC National Root CA) và chứng thư nhà cung cấp vào đây.
    macOS: chuỗi khoá hệ thống; Linux: kho chứng thư của hệ điều hành."""
    if "v" in _SYSTEM_CERTS:
        return _SYSTEM_CERTS["v"]
    roots, inter = [], []
    try:
        if sys.platform.startswith("win"):
            import ssl
            from asn1crypto import x509
            for store, dest in (("ROOT", roots), ("CA", inter)):
                try:
                    items = ssl.enum_certificates(store)
                except Exception:
                    continue
                for der, enc, _trust in items:
                    if enc == "x509_asn":
                        try:
                            dest.append(x509.Certificate.load(der))
                        except Exception:
                            pass
        elif sys.platform == "darwin":
            import subprocess
            for kc, dest in (("/System/Library/Keychains/SystemRootCertificates.keychain", roots),
                             ("/Library/Keychains/System.keychain", roots),
                             (os.path.expanduser("~/Library/Keychains/login.keychain-db"), inter)):
                if os.path.exists(kc):
                    r = subprocess.run(["security", "find-certificate", "-a", "-p", kc], capture_output=True, timeout=20)
                    dest += _load_certs(r.stdout)
        else:
            for f in ("/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt", "/etc/ssl/cert.pem"):
                if os.path.exists(f):
                    roots += _load_certs(open(f, "rb").read())
                    break
    except Exception:
        pass
    _SYSTEM_CERTS["v"] = (roots, inter)
    return roots, inter


def count_signatures(data: bytes) -> int:
    try:
        from pyhanko.pdf_utils.reader import PdfFileReader
        return len(PdfFileReader(io.BytesIO(data), strict=False).embedded_signatures)
    except Exception:
        return 0


def verify_signatures(data: bytes, trust_dir: str | None = None) -> list[dict]:
    """Kiểm tra mọi chữ ký số trong PDF."""
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko_certvalidator import ValidationContext

    try:
        reader = PdfFileReader(io.BytesIO(data), strict=False)
        sigs = list(reader.embedded_signatures)
    except Exception as e:
        raise SignError(f"Không đọc được chữ ký trong file: {e}")
    # gốc tin cậy = chứng thư người dùng tự thêm + chứng thư gốc có sẵn trong máy; chứng thư trung gian (Viettel-CA,
    # VNPT-CA…) của máy giúp nối chữ ký tới gốc khi file ký không kèm đủ chuỗi chứng thư
    sys_roots, sys_inter = system_certs()
    roots = _load_trust(trust_dir) + sys_roots
    results = []
    for sig in sigs:
        res = {"field": sig.field_name, "ok": False, "intact": False, "valid": False, "trusted": False,
               "whole": False, "modified": "", "time": None, "tsa": False, "error": "", "info": {},
               "reason": "", "location": ""}
        try:
            cert = sig.signer_cert
            if cert is not None:
                res["info"] = cert_info(cert)
            so = sig.sig_object
            res["reason"] = str(so.get("/Reason", "") or "")
            res["location"] = str(so.get("/Location", "") or "")
        except Exception:
            pass
        try:
            vc = ValidationContext(extra_trust_roots=roots or None, other_certs=sys_inter or None, allow_fetching=False)
            st = validate_pdf_signature(sig, vc, skip_diff=False)
            res["intact"] = bool(st.intact)
            res["valid"] = bool(st.valid)
            res["trusted"] = bool(st.trusted)
            res["time"] = st.signer_reported_dt
            res["tsa"] = st.timestamp_validity is not None
            if st.timestamp_validity is not None and st.timestamp_validity.timestamp:
                res["time"] = st.timestamp_validity.timestamp
            cov = getattr(st, "coverage", None)
            res["whole"] = bool(cov is not None and cov.name == "ENTIRE_FILE")
            lvl = getattr(st, "modification_level", None)
            if not res["whole"]:
                lname = lvl.name if lvl is not None else ""
                res["modified"] = {"NONE": "", "LTA_UPDATES": "", "FORM_FILLING": "có ký thêm/điền form sau khi ký (hợp lệ)",
                                   "ANNOTATIONS": "có thêm ghi chú sau khi ký",
                                   "OTHER": "NỘI DUNG ĐÃ BỊ THAY ĐỔI sau khi ký"}.get(lname, lname)
                res["bad_change"] = lname == "OTHER"
            res["ok"] = res["intact"] and res["valid"] and not res.get("bad_change")
        except Exception as e:
            res["error"] = f"{type(e).__name__}: {e}"
        results.append(res)
    return results
