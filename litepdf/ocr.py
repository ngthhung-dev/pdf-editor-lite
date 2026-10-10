"""Nhận dạng chữ (OCR) bằng nhiều bộ máy: Tesseract, RapidOCR (model PaddleOCR chạy trên máy) và Gemini (trên mạng).

RapidOCR và Gemini trả về từng dòng chữ kèm vị trí; app đặt một lớp chữ ẩn lên đúng chỗ đó trên TRANG GỐC,
nên hình ảnh trang giữ nguyên độ nét và dung lượng gần như không tăng.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import os
import re
import time
import urllib.error
import urllib.parse

import pymupdf

from . import tools
from . import translate as T

RAPID_LANGS = [("latin", "Tiếng Việt / chữ Latin có dấu (tải model ~10 MB ở lần đầu)"),
               ("multi", "Tiếng Anh, số, Trung – Nhật (model có sẵn, không cần mạng)")]


class OcrError(Exception):
    pass


def rapid_available() -> bool:
    if tools.FROZEN:      # bản cài đặt: RapidOCR là thành phần tuỳ chọn, có mặt khi thư mục dữ liệu của nó được cài
        import sys
        base = getattr(sys, "_MEIPASS", "")
        return os.path.isfile(os.path.join(base, "rapidocr", "config.yaml")) and os.path.isdir(os.path.join(base, "onnxruntime"))
    return importlib.util.find_spec("rapidocr") is not None and importlib.util.find_spec("onnxruntime") is not None


# ------------------------------------------------------------------ lớp chữ ẩn
def has_text(page) -> bool:
    try:
        return len(page.get_text("text").strip()) > 20
    except Exception:
        return False


def add_text_layer(page, lines: list[tuple[tuple[float, float, float, float], str]], scale: float) -> int:
    """Đặt chữ ẩn (chọn/tìm/sao chép được) vào các khung dòng. Toạ độ khung tính bằng điểm ảnh, scale = 72/dpi."""
    n = 0
    fonts: dict[str, str] = {}
    for (x0, y0, x1, y1), text in lines:
        text = " ".join(str(text).split())
        w, h = (x1 - x0) * scale, (y1 - y0) * scale
        if not text or w < 2 or h < 2 or (h > 2.5 * w and len(text) > 2):
            continue
        try:
            font, path = tools.pick_font_file("Arial", 0, text)
        except Exception:
            font, path = pymupdf.Font("helv"), None
        size = max(3.0, min(h * 0.78, 72))
        try:
            tw = font.text_length(text, size) or 1
        except Exception:
            tw = w
        pt = pymupdf.Point(x0 * scale, y1 * scale - 0.22 * h)
        kw = {}
        if path:
            name = fonts.setdefault(path, f"ocr{len(fonts)}")
            kw = {"fontname": name, "fontfile": path}
        try:
            page.insert_text(pt, text, fontsize=size, render_mode=3, morph=(pt, pymupdf.Matrix(w / tw, 1)), **kw)
            n += 1
        except Exception:
            try:       # phông vừa chọn không nhúng được (file .ttc, ký hiệu lạ...): dùng phông dựng sẵn để dòng vẫn chọn được
                tw2 = pymupdf.get_text_length(text, "helv", size) or w
                page.insert_text(pt, text, fontsize=size, render_mode=3, morph=(pt, pymupdf.Matrix(w / tw2, 1)))
                n += 1
            except Exception:
                pass
    return n


def _render(page, dpi: int):
    return page.get_pixmap(dpi=dpi, alpha=False)


# ------------------------------------------------------------------ RapidOCR
_rapid: dict[str, object] = {}


def rapid_engine(lang: str, model_dir: str):
    if lang not in _rapid:
        from rapidocr import RapidOCR
        params = {"Global.log_level": "error"}
        if lang == "latin":
            from rapidocr.utils.typings import LangRec, ModelType, OCRVersion
            if tools.FROZEN:      # bản cài đặt: model kèm sẵn; nếu thiếu thì tải về thư mục dữ liệu (thư mục app không ghi được)
                import rapidocr
                own = os.path.join(os.path.dirname(rapidocr.__file__), "models", "latin_PP-OCRv5_rec_mobile.onnx")
                if not os.path.exists(own) and model_dir:
                    os.makedirs(model_dir, exist_ok=True)
                    params["Global.model_root_dir"] = model_dir
            params.update({"Rec.lang_type": LangRec.LATIN,
                           "Rec.ocr_version": OCRVersion.PPOCRV5, "Rec.model_type": ModelType.MOBILE})
        try:
            import numpy as np
            eng = RapidOCR(params=params)
            import cv2
            probe = np.full((80, 360, 3), 255, np.uint8)
            cv2.putText(probe, "Test 123", (20, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 0), 3)
            eng(probe)                                    # nạp (và tải, nếu thiếu) model ngay bây giờ để báo lỗi rõ ràng
            _rapid[lang] = eng
        except Exception as e:
            if lang == "latin":
                raise OcrError("Không tải được model tiếng Việt/Latin của RapidOCR (cần mạng ở lần đầu, tải từ modelscope.cn).\n"
                               "Kiểm tra mạng rồi thử lại, hoặc tạm dùng Tesseract / Gemini.\n\nChi tiết: " + str(e)[:300])
            raise OcrError("Không khởi động được RapidOCR: " + str(e)[:300])
    return _rapid[lang]


def pix_array(pix):
    import numpy as np
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3][:, :, ::-1].copy()   # RGB → BGR


def rapid_lines(engine, img, min_score: float = 0.0) -> list:
    r = engine(img)
    out = []
    if r is None or r.boxes is None or r.txts is None:
        return out
    scores = r.scores if getattr(r, "scores", None) is not None else [1.0] * len(r.txts)
    for box, text, sc in zip(r.boxes, r.txts, scores):
        if sc is not None and float(sc) < min_score:
            continue                                  # chữ quá mờ, đọc không chắc: bỏ qua
        xs, ys = [float(p[0]) for p in box], [float(p[1]) for p in box]
        out.append(((min(xs), min(ys), max(xs), max(ys)), text))
    return out


def tess_lines(pix, lang: str) -> list:
    """Các dòng chữ Tesseract đọc được trong ảnh, kèm khung (điểm ảnh)."""
    one = pymupdf.open("pdf", pix.pdfocr_tobytes(language=lang, tessdata=tools.find_tessdata()))
    try:
        pg = one[0]
        kx, ky = pix.width / max(1, pg.rect.width), pix.height / max(1, pg.rect.height)
        out = []
        for b in pg.get_text("dict").get("blocks", []):
            for ln in b.get("lines", []):
                text = "".join(sp["text"] for sp in ln["spans"]).strip()
                if text:
                    x0, y0, x1, y1 = ln["bbox"]
                    out.append(((x0 * kx, y0 * ky, x1 * kx, y1 * ky), text))
        return out
    finally:
        one.close()


def make_reader(kind: str, opts: dict, offload=None, note=None, min_score: float = 0.0):
    """Hàm read(pix) -> [(khung điểm ảnh, chữ)]. Phần dùng PyMuPDF chạy ở luồng gọi; phần nặng/chờ mạng đi qua offload."""
    run_it = offload or (lambda fn: fn())
    if kind == "tesseract":
        lang = opts.get("lang") or "eng"
        return lambda pix: tess_lines(pix, lang)
    if kind == "rapid":
        if note:
            note("Đang nạp model RapidOCR…")
        eng = run_it(lambda: rapid_engine(opts.get("lang", "latin"), opts.get("model_dir", "")))

        def read_rapid(pix):
            img = pix_array(pix)
            return run_it(lambda: rapid_lines(eng, img, min_score))
        return read_rapid
    eng = opts["gemini"]

    def pack(pix):
        return pix.tobytes("jpeg", jpg_quality=85), pix.width, pix.height

    def read_gemini(pix):
        item = pack(pix)
        return run_it(lambda: gemini_lines_many(eng, [item], note)[0])
    read_gemini.pack = pack                          # gom nhiều hình vào một lượt gọi để đỡ tốn lượt
    read_gemini.many = lambda items: run_it(lambda: gemini_lines_many(eng, items, note))
    read_gemini.batch = 4
    return read_gemini


# ------------------------------------------------------------------ Gemini
GEMINI_PROMPT = (
    "You are an OCR engine. Transcribe ALL text visible on this scanned page exactly as printed, one item per text line, "
    "in natural reading order. Keep the original language, spelling, diacritics, numbers and punctuation; do not translate, "
    "correct, summarise or invent text; skip stamps/signature scribbles that are not readable text. "
    "If a piece of text is too blurry or too small to read with confidence, leave it out instead of guessing. "
    "Write formulas with Unicode characters, not LaTeX: superscripts and subscripts (x², aⁿ⁻¹, x₁, fₓ), primes (f′, f″), "
    "∂ ∫ √ → ↦ ≤ ≥ ∞, and combining marks for an overline or arrow above letters (F̅X̅, F⃗X⃗); e.g. ∂f/∂x₁, √(ax+b). "
    "A line that contains only a formula is still one item of its own; never join it with the next line. "
    "One item per printed line: never merge several lines or a whole paragraph into one item. "
    "Return ONLY a JSON array; each item is {\"box_2d\": [ymin, xmin, ymax, xmax], \"text\": \"...\"} where box_2d is the "
    "tight bounding box of that line, normalised to 0-1000 relative to the image height (y) and width (x).")


_BAD_ESC = re.compile(r'\\(?!["\\/bfnrtu])')
_ITEM = re.compile(r'"box_2d"\s*:\s*\[([^\]]*)\].*?"text"\s*:\s*"((?:[^"\\]|\\.)*)"', re.S)
_ITEM2 = re.compile(r'"text"\s*:\s*"((?:[^"\\]|\\.)*)".*?"box_2d"\s*:\s*\[([^\]]*)\]', re.S)
_IMG_NO = re.compile(r'"image"\s*:\s*(\d+)')
last_raw = {"text": ""}      # câu trả lời gần nhất của Gemini (để chẩn đoán khi nhận dạng thiếu dòng)


def _unescape(sv: str) -> str:
    try:
        return json.loads('"' + _BAD_ESC.sub(r"\\\\", sv) + '"')
    except Exception:
        return sv.replace('\\"', '"').replace("\\n", " ")


def parse_items(text: str) -> list:
    """Đọc danh sách {box_2d, text} từ câu trả lời của AI, kể cả khi JSON không chuẩn: có dấu \\ của công thức toán
    (\\frac, \\int...), có dấu { } trong chữ, hoặc bị cắt giữa chừng."""
    t = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text.strip()).strip()
    for cand in (t, _BAD_ESC.sub(r"\\\\", t)):
        try:
            j = json.loads(cand)
            if isinstance(j, dict):
                j = next((v for v in j.values() if isinstance(v, list)), [])
            if isinstance(j, list):
                return [x for x in j if isinstance(x, dict)]
        except Exception:
            pass
    out = []
    for chunk in re.split(r'\}\s*,\s*(?=\{\s*")', t):       # nhặt từng mục một (dấu { } bên trong chữ không làm tách nhầm)
        m = _ITEM.search(chunk)
        box, txt = (m.group(1), m.group(2)) if m else (None, None)
        if not m:
            m = _ITEM2.search(chunk)
            if not m:
                continue
            box, txt = m.group(2), m.group(1)
        try:
            nums = [float(v) for v in box.split(",")]
        except ValueError:
            continue
        if len(nums) != 4:
            continue
        item = {"box_2d": nums, "text": _unescape(txt)}
        k = _IMG_NO.search(chunk)
        if k:
            item["image"] = int(k.group(1))
        out.append(item)
    return out


def _split_tall(lines: list) -> list:
    """AI đôi khi gộp cả đoạn nhiều dòng vào một khung cao: chia lại thành từng dòng để chữ ẩn nằm đúng trên chữ thật."""
    hs = sorted(y1 - y0 for (x0, y0, x1, y1), t in lines if len(str(t)) > 3)
    if len(hs) < 3:
        return lines
    med = hs[len(hs) // 3] or 1          # chiều cao một dòng điển hình (lấy thiên về nhỏ)
    out = []
    for (x0, y0, x1, y1), t in lines:
        k = int(round((y1 - y0) / (med * 1.15)))
        words = str(t).split()
        if k < 2 or len(words) < 2 * k:
            out.append(((x0, y0, x1, y1), t))
            continue
        per = -(-len(words) // k)
        h = (y1 - y0) / k
        for i in range(k):
            part = " ".join(words[i * per:(i + 1) * per])
            if part:
                out.append(((x0, y0 + i * h, x1, y0 + (i + 1) * h), part))
    return out


def gemini_lines(engine, data: bytes, width: int, height: int, note=None) -> list:
    """data: ảnh JPEG của trang/hình. Chỉ gọi mạng, không đụng tới PyMuPDF (chạy được ở luồng phụ)."""
    return gemini_lines_many(engine, [(data, width, height)], note)[0]


MANY_NOTE = ("\nThere are {n} images, each preceded by a label 'Image k'. Add the field \"image\": k (1-based) to every item "
             "so each line is attributed to the image it was read from; box_2d is relative to THAT image.")


def gemini_lines_many(engine, images: list[tuple[bytes, int, int]], note=None) -> list[list]:
    """Đọc chữ của nhiều ảnh trong MỘT lượt gọi (gói miễn phí giới hạn số lượt mỗi phút). Trả về danh sách dòng cho từng ảnh."""
    waits = 0
    for _ in range(30):
        engine._check()
        model = engine.pick_model()
        cfg = {"temperature": 0, "maxOutputTokens": 32000, "responseMimeType": "application/json"}
        if getattr(engine, "ocr_schema", True):
            props = {"box_2d": {"type": "ARRAY", "items": {"type": "INTEGER"}}, "text": {"type": "STRING"}}
            if len(images) > 1:
                props["image"] = {"type": "INTEGER"}
            cfg["responseSchema"] = {"type": "ARRAY", "items": {"type": "OBJECT", "properties": props,
                                                                "required": list(props)}}
        if engine.use_thinking_cfg:
            m = re.search(r"gemini-(\d+)(?:\.(\d+))?", model)
            if m and int(m.group(1)) >= 3:
                cfg["thinkingConfig"] = {"thinkingLevel": "low"}
            elif m and (int(m.group(1)), int(m.group(2) or 0)) >= (2, 5):
                cfg["thinkingConfig"] = {"thinkingBudget": 0}
        parts = []
        for k, (data, _w, _h) in enumerate(images):
            if len(images) > 1:
                parts.append({"text": f"Image {k + 1}:"})
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(data).decode("ascii")}})
        parts.append({"text": GEMINI_PROMPT + (MANY_NOTE.format(n=len(images)) if len(images) > 1 else "")})
        body = {"contents": [{"role": "user", "parts": parts}], "generationConfig": cfg}
        url = f"{engine.base}/models/{urllib.parse.quote(model)}:generateContent"
        try:
            raw = T._http(url, json.dumps(body).encode("utf-8"),
                          {"Content-Type": "application/json", "x-goog-api-key": engine.key}, timeout=120)
            j = json.loads(raw)
            cands = j.get("candidates") or []
            if not cands:
                return [[] for _ in images]
            text = "".join(p.get("text", "") for p in (cands[0].get("content") or {}).get("parts", []))
            last_raw["text"] = text
            items = parse_items(text)
            engine.used.add(model)
            engine.main = engine.main or model
            out = [[] for _ in images]
            for it in items if isinstance(items, list) else []:
                try:
                    y0, x0, y1, x1 = [float(v) for v in it["box_2d"]]
                    txt = str(it.get("text", "")).strip()
                    k = int(it.get("image", 1)) - 1
                except Exception:
                    continue
                if txt and x1 > x0 and y1 > y0 and 0 <= k < len(images):
                    out[k].append(((x0, y0, x1, y1), txt))
            for k, rows in enumerate(out):
                width, height = images[k][1], images[k][2]
                # chuẩn là thang 0–1000; có model lại trả toạ độ theo điểm ảnh → nhận ra khi có số vượt 1000
                big = max((max(b) for b, _t in rows), default=0)
                sx, sy = (1.0, 1.0) if big > 1000.5 else (width / 1000, height / 1000)
                out[k] = _split_tall([((x0 * sx, y0 * sy, x1 * sx, y1 * sy), t) for (x0, y0, x1, y1), t in rows])
            return out
        except urllib.error.HTTPError as e:
            msg = T._http_error_text(e)
            low = msg.lower()
            if e.code in (400, 401, 403) and ("api key" in low or "api_key" in low):
                raise OcrError("Google báo API key không hợp lệ.\n" + msg)
            if e.code == 400 and engine.use_thinking_cfg and "thinking" in low:
                engine.use_thinking_cfg = False
                continue
            if e.code == 400 and getattr(engine, "ocr_schema", True) and ("schema" in low or "mime" in low or "json" in low):
                engine.ocr_schema = False        # model không nhận khuôn JSON: gọi lại kiểu thường
                continue
            if (e.code in (403, 404) or (e.code == 429 and "limit: 0" in low)) and not engine.fixed:
                engine._bad[model] = f"lỗi {e.code}"
                engine.model = ""
                continue
            if e.code == 429 or e.code >= 500:
                if e.code == 429 and ("perday" in low.replace(" ", "").replace("_", "") or "per day" in low) and not engine.fixed:
                    engine._bad[model] = "đã hết lượt gọi miễn phí của hôm nay"
                    engine.model = ""
                    continue
                waits += 1
                if waits > 8:
                    raise OcrError("Gemini báo hết lượt gọi của gói miễn phí hoặc máy chủ đang bận. Thử lại sau ít phút.\n" + msg)
                wait = 20.0 * waits
                m = re.search(r"retry in ([\d.]+)s", msg)
                if m:
                    wait = min(90, float(m.group(1)) + 2)
                if engine.fast and not engine.fixed:      # "Ưu tiên tốc độ": model này hết lượt thì dùng tạm model khác
                    engine._cool[model] = time.time() + wait
                    others = [x for x in engine.candidates() if x not in engine._bad and x != model
                              and engine._cool.get(x, 0) <= time.time()]
                    if others:
                        engine.model = ""
                        waits -= 1
                        continue
                    wait = max(1.0, min(engine._cool.values()) - time.time())
                engine._sleep(wait, (lambda s: note(f"Hết lượt gọi miễn phí trong phút này, tự chạy tiếp sau {s} giây…")) if note else None)
                continue
            raise OcrError(f"Gemini báo lỗi {e.code} với model {model}: {msg}")
        except urllib.error.URLError as e:
            if T.is_timeout(e) and not engine.fixed and len(engine._bad) < 3:
                engine._bad[model] = "không trả lời sau 120 giây"
                engine.model = ""
                continue
            raise OcrError(f"Không kết nối được tới máy chủ Gemini của Google. Kiểm tra mạng.\nChi tiết: {e.reason}")
    raise OcrError("Gemini không phản hồi.")


# ------------------------------------------------------------------ chạy cả tài liệu
def run(data: bytes, engine: str, opts: dict, progress=None, note=None, cancel=None, offload=None) -> tuple[bytes, dict]:
    """OCR bản sao của tài liệu. engine: tesseract | rapid | gemini. Trả về (PDF mới, thống kê)."""
    doc = pymupdf.open(stream=data, filetype="pdf")
    stats = {"pages": 0, "lines": 0, "skipped": 0, "empty": []}
    dpi = int(opts.get("dpi", 300))
    only_scans = bool(opts.get("only_scans", True))
    try:
        if engine == "tesseract":
            out = pymupdf.open()
            for i, page in enumerate(doc):
                if cancel and cancel():
                    raise T.Cancelled()
                if only_scans and has_text(page):
                    out.insert_pdf(doc, from_page=i, to_page=i)
                    stats["skipped"] += 1
                else:
                    pix = _render(page, dpi)
                    try:
                        one = pymupdf.open("pdf", pix.pdfocr_tobytes(language=opts.get("lang", "eng"), tessdata=tools.find_tessdata()))
                    except Exception as e:
                        raise OcrError(f"OCR lỗi ở trang {i + 1}: {e}")
                    out.insert_pdf(one)
                    one.close()
                    stats["pages"] += 1
                if progress:
                    progress(i + 1, doc.page_count)
            res = out.tobytes(garbage=3, deflate=True)
            out.close()
            return res, stats
        if engine != "rapid":
            dpi = min(dpi, 200)          # ảnh gửi lên mạng: 200 DPI là đủ nét, nhẹ và nhanh hơn
        read = make_reader(engine, opts, offload, note)
        for i in range(doc.page_count):
            if cancel and cancel():
                raise T.Cancelled()
            page = doc[i]
            if only_scans and has_text(page):
                stats["skipped"] += 1
            else:
                if page.rotation:
                    page.remove_rotation()
                    page = doc[i]
                pix = _render(page, dpi)
                t0 = time.time()
                try:
                    lines = read(pix)
                except (OcrError, T.TranslateError):
                    raise
                except Exception as e:
                    raise OcrError(f"OCR lỗi ở trang {i + 1}: {str(e)[:300]}")
                n = add_text_layer(page, lines, 72.0 / dpi)
                stats["pages"] += 1
                stats["lines"] += n
                stats["read"] = stats.get("read", 0) + len(lines)
                if not n:
                    stats["empty"].append(i)
                stats["last_secs"] = time.time() - t0
            if progress:
                progress(i + 1, doc.page_count)
        tools.finalize_fonts(doc)
        return doc.tobytes(garbage=3, deflate=True), stats
    finally:
        doc.close()
