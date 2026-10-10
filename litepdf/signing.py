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
        if k not in seen and not os.path.basename(p).lower().startswith(("p11-kit", "libp11-kit", "msp", "wp")):
            seen.add(k)
            out.append(p)
    return out


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
def make_appearance(width: float, height: float, lines: list[str], image_path: str | None = None,
                    border: bool = True, color=(0.75, 0.05, 0.05)) -> bytes:
    """Dựng hình khung chữ ký (PDF 1 trang) gồm ảnh chữ ký và các dòng thông tin."""
    doc = pymupdf.open()
    page = doc.new_page(width=width, height=height)
    r = page.rect
    if border:
        page.draw_rect(r + (0.6, 0.6, -0.6, -0.6), color=color, width=1.0)
    pad = 3
    text_rect = r + (pad, pad, -pad, -pad)
    if image_path and os.path.exists(image_path):
        if lines:
            if width >= height * 1.6:
                img_rect = pymupdf.Rect(pad, pad, width * 0.4, height - pad)
                text_rect = pymupdf.Rect(width * 0.4 + pad, pad, width - pad, height - pad)
            else:
                img_rect = pymupdf.Rect(pad, pad, width - pad, height * 0.5)
                text_rect = pymupdf.Rect(pad, height * 0.5, width - pad, height - pad)
        else:
            img_rect = text_rect
        try:
            page.insert_image(img_rect, filename=image_path, keep_proportion=True)
        except Exception:
            pass
    if lines:
        text = "\n".join(lines)
        font = tools.pick_font("arial", 0, text)
        size = 11.0
        while size > 3.5:
            tw = pymupdf.TextWriter(r, color=color)
            try:
                left = tw.fill_textbox(text_rect, text, font=font, fontsize=size, lineheight=1.15)
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
def _load_trust(trust_dir: str | None) -> list:
    roots = []
    if trust_dir and os.path.isdir(trust_dir):
        from asn1crypto import pem, x509
        for f in os.listdir(trust_dir):
            if not f.lower().endswith((".cer", ".crt", ".pem", ".der")):
                continue
            try:
                raw = open(os.path.join(trust_dir, f), "rb").read()
                if pem.detect(raw):
                    for _t, _h, der in pem.unarmor(raw, multiple=True):
                        roots.append(x509.Certificate.load(der))
                else:
                    roots.append(x509.Certificate.load(raw))
            except Exception:
                continue
    return roots


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
    roots = _load_trust(trust_dir)
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
            vc = ValidationContext(extra_trust_roots=roots or None, allow_fetching=False)
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
