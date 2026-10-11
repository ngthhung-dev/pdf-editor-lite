"""Dịch tài liệu PDF sang ngôn ngữ khác, thay chữ tại chỗ để giữ bố cục."""
from __future__ import annotations

import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import pymupdf

from . import tools

LANGS = [  # (mã, tên tiếng Việt, tên tiếng Anh dùng trong câu lệnh cho AI)
    ("vi", "Tiếng Việt", "Vietnamese"), ("en", "Tiếng Anh", "English"), ("zh-CN", "Tiếng Trung (giản thể)", "Simplified Chinese"),
    ("zh-TW", "Tiếng Trung (phồn thể)", "Traditional Chinese"), ("ja", "Tiếng Nhật", "Japanese"), ("ko", "Tiếng Hàn", "Korean"),
    ("fr", "Tiếng Pháp", "French"), ("de", "Tiếng Đức", "German"), ("es", "Tiếng Tây Ban Nha", "Spanish"),
    ("pt", "Tiếng Bồ Đào Nha", "Portuguese"), ("it", "Tiếng Ý", "Italian"), ("ru", "Tiếng Nga", "Russian"),
    ("th", "Tiếng Thái", "Thai"), ("lo", "Tiếng Lào", "Lao"), ("km", "Tiếng Khmer", "Khmer"), ("id", "Tiếng Indonesia", "Indonesian"),
    ("ms", "Tiếng Mã Lai", "Malay"), ("tl", "Tiếng Philippines", "Filipino"), ("my", "Tiếng Miến Điện", "Burmese"),
    ("hi", "Tiếng Hindi", "Hindi"), ("ar", "Tiếng Ả Rập", "Arabic"), ("tr", "Tiếng Thổ Nhĩ Kỳ", "Turkish"),
    ("nl", "Tiếng Hà Lan", "Dutch"), ("pl", "Tiếng Ba Lan", "Polish"), ("sv", "Tiếng Thuỵ Điển", "Swedish"),
    ("cs", "Tiếng Séc", "Czech"), ("uk", "Tiếng Ukraina", "Ukrainian"), ("el", "Tiếng Hy Lạp", "Greek"),
    ("he", "Tiếng Do Thái", "Hebrew"), ("hu", "Tiếng Hungary", "Hungarian"), ("da", "Tiếng Đan Mạch", "Danish"),
    ("fi", "Tiếng Phần Lan", "Finnish"), ("no", "Tiếng Na Uy", "Norwegian"), ("ro", "Tiếng Rumani", "Romanian"),
]
DOMAINS = [
    ("general", "Chung", "general documents"),
    ("legal", "Pháp lý, hợp đồng", "legal documents and contracts"),
    ("finance", "Tài chính, kế toán, thuế", "finance, accounting and tax documents"),
    ("technical", "Kỹ thuật, hướng dẫn sử dụng", "technical documentation and user manuals"),
    ("it", "Công nghệ thông tin", "information technology and software"),
    ("medical", "Y khoa, dược", "medical and pharmaceutical documents"),
    ("business", "Kinh doanh, thương mại", "business and commercial correspondence"),
    ("academic", "Học thuật, nghiên cứu", "academic and scientific papers"),
    ("construction", "Xây dựng, kiến trúc", "construction and architecture"),
]
GEMINI_DEFAULT = "gemini-3.8-flash"


class TranslateError(Exception):
    pass


class Cancelled(Exception):
    pass


class TooSlow(TranslateError):
    """Lô gửi đi quá lớn nên máy chủ trả lời không kịp: chia nhỏ rồi gửi lại."""


def lang_name(code_or_name: str) -> tuple[str, str]:
    """(mã, tên tiếng Anh) từ mã hoặc tên người dùng gõ."""
    t = code_or_name.strip()
    for code, vi, en in LANGS:
        if t.lower() in (code.lower(), vi.lower(), en.lower()):
            return code, en
    return t, t


# =============================================================== tách chữ
_LETTERS = re.compile(r"[^\W\d_]", re.UNICODE)
_URLISH = re.compile(r"^\s*(https?://\S+|www\.\S+|\S+@\S+\.\S+)\s*$", re.I)
_LEADER = re.compile(r"^(?P<title>.+?)(?P<dots>\s*(?:[.…·•_]\s?){4,}\s*)(?P<ref>\S{1,12})?\s*$")


def translatable(text: str) -> bool:
    t = text.strip()
    return len(_LETTERS.findall(t)) >= 2 and not _URLISH.match(t)


def _rgb(c: int) -> tuple[float, float, float]:
    return ((c >> 16) & 255) / 255, ((c >> 8) & 255) / 255, (c & 255) / 255


def _style(spans: list[dict]) -> dict:
    main = max(spans, key=lambda sp: len(sp["text"].strip()))
    n = sum(len(sp["text"]) for sp in spans) or 1
    bold = sum(len(sp["text"]) for sp in spans if sp["flags"] & 16 or "bold" in sp["font"].lower()) / n > 0.6
    ital = sum(len(sp["text"]) for sp in spans if sp["flags"] & 2 or "italic" in sp["font"].lower()
               or "oblique" in sp["font"].lower()) / n > 0.6
    return {"size": main["size"], "color": _rgb(main["color"]), "font": main["font"], "flags": main["flags"],
            "bold": bold, "italic": ital}


def _segments(line: dict) -> list[list[dict]]:
    """Tách một dòng thành các cụm cách xa nhau (ô bảng, cột, số trang ở cuối dòng...)."""
    spans = [sp for sp in line["spans"] if sp["text"].strip()]
    spans.sort(key=lambda sp: sp["bbox"][0])
    segs: list[list[dict]] = []
    for sp in spans:
        if segs:
            prev = segs[-1][-1]
            gap = sp["bbox"][0] - prev["bbox"][2]
            if gap > max(1.6 * prev["size"], 12):
                segs.append([sp])
                continue
        if segs:
            segs[-1].append(sp)
        else:
            segs.append([sp])
    return segs


def _join(spans: list[dict]) -> str:
    out = ""
    for k, sp in enumerate(spans):
        if k and sp["bbox"][0] - spans[k - 1]["bbox"][2] > 0.25 * sp["size"] and not out.endswith(" ") \
                and not sp["text"].startswith(" "):
            out += " "
        out += sp["text"]
    return " ".join(out.split())


# ---- định dạng trong dòng: chữ đậm / nghiêng / gạch dưới / đổi màu ở MỘT PHẦN của đoạn
_TAG = re.compile(r"<\s*(/?)\s*g\s*(\d+)\s*>", re.I)
_meas = None


def strip_marks(text: str) -> str:
    return " ".join(_TAG.sub("", text).split()) if "<" in text else text


def _underlines(page) -> list[pymupdf.Rect]:
    """Các nét kẻ ngang mảnh trên trang (ứng viên là nét gạch dưới chữ)."""
    out: list[pymupdf.Rect] = []
    if page.rotation:
        return out
    try:
        drawings = page.get_drawings()
    except Exception:
        return out
    for d in drawings:
        w = d.get("width") or 0.6
        for it in d.get("items", []):
            if it[0] == "l" and "s" in d.get("type", ""):
                a, b = it[1], it[2]
                if abs(a.y - b.y) < 0.6 and abs(a.x - b.x) >= 3 and w <= 2.5:
                    out.append(pymupdf.Rect(min(a.x, b.x), a.y - w / 2, max(a.x, b.x), a.y + w / 2))
            elif it[0] in ("re", "qu") and "f" in d.get("type", ""):
                r = pymupdf.Rect(it[1]) if it[0] == "re" else it[1].rect
                r.normalize()
                if r.height <= 2.0 and r.width >= 3:
                    out.append(r)
    return out


def _cut(sp: dict, a: float, b: float) -> tuple[int, int]:
    """Khoảng ký tự của span nằm trong đoạn ngang [a, b] (ước lượng theo bề rộng chữ, làm tròn về ranh giới từ)."""
    global _meas
    text = sp["text"]
    x0, x1 = sp["bbox"][0], sp["bbox"][2]
    if not text or x1 <= x0:
        return 0, 0
    if a <= x0 + 0.08 * (x1 - x0) and b >= x1 - 0.08 * (x1 - x0):
        return 0, len(text)
    if _meas is None:
        _meas = pymupdf.Font("helv")
    ws = [_meas.text_length(ch, 10) or 5 for ch in text]
    k = (x1 - x0) / (sum(ws) or 1)
    pos = [x0]
    for w in ws:
        pos.append(pos[-1] + w * k)
    i0 = min(range(len(pos)), key=lambda i: abs(pos[i] - a))
    i1 = min(range(len(pos)), key=lambda i: abs(pos[i] - b))

    def snap(i):   # nét gạch dưới gần như luôn ôm trọn từ: kéo về ranh giới từ gần nhất (lệch tối đa 2 ký tự)
        for dlt in (0, 1, -1, 2, -2):
            j = i + dlt
            if 0 <= j <= len(text) and (j == 0 or j == len(text) or text[j - 1].isspace() or text[j].isspace()):
                return j
        return i
    i0, i1 = snap(i0), snap(i1)
    return (i0, i1) if i1 > i0 else (0, 0)


def _mark_underlines(lines: list[dict], ulines: list[pymupdf.Rect]) -> list[pymupdf.Rect]:
    """Gắn sp["_ul"] = [(i0, i1), ...] cho các span có nét gạch dưới; trả về các nét đã khớp (để xoá khi dịch)."""
    used: list[pymupdf.Rect] = []
    if not ulines:
        return used
    for ln in lines:
        spans = [sp for sp in ln["spans"] if sp["text"].strip()]
        if not spans:
            continue
        lx0, lx1 = min(sp["bbox"][0] for sp in spans), max(sp["bbox"][2] for sp in spans)
        for u in ulines:
            cy = (u.y0 + u.y1) / 2
            if u.x0 < lx0 - 2.5 or u.x1 > lx1 + 2.5:
                continue                      # dài hơn dòng chữ: là đường kẻ trang trí/khung bảng, không phải gạch dưới
            hit = False
            for sp in spans:
                base, size = sp["origin"][1], sp["size"]
                if not (base + 0.01 * size <= cy <= base + 0.32 * size):
                    continue
                a, b = max(u.x0, sp["bbox"][0]), min(u.x1, sp["bbox"][2])
                if b - a < 1.5:
                    continue
                i0, i1 = _cut(sp, a, b)
                if i1 > i0:
                    sp.setdefault("_ul", []).append((i0, i1))
                    hit = True
            if hit:
                used.append(pymupdf.Rect(u))
    return used


def _is_bold(sp):
    return bool(sp["flags"] & 16) or "bold" in sp["font"].lower()


def _is_ital(sp):
    f = sp["font"].lower()
    return bool(sp["flags"] & 2) or "italic" in f or "oblique" in f


def _runs(lines_spans: list[list[dict]]) -> list[list]:
    """[[chữ, (đậm, nghiêng, gạch dưới, màu), khung gốc], ...] theo thứ tự đọc; ghép lại đúng bằng chữ của đoạn."""
    runs: list[list] = []

    def add(text, attrs, rect):
        if not text:
            return
        if runs and runs[-1][1] == attrs:
            runs[-1][0] += text
            if rect is not None:
                runs[-1][2] = (runs[-1][2] | rect) if runs[-1][2] is not None else rect
        else:
            runs.append([text, attrs, rect])
    for li, spans in enumerate(lines_spans):
        if li:
            add(" ", runs[-1][1] if runs else None, None)
        for k, sp in enumerate(spans):
            text = sp["text"]
            if k and sp["bbox"][0] - spans[k - 1]["bbox"][2] > 0.25 * sp["size"] and not text.startswith(" ") \
                    and not spans[k - 1]["text"].endswith(" "):
                add(" ", runs[-1][1] if runs else None, None)
            marks = [False] * len(text)
            for i0, i1 in sp.get("_ul", []):
                for i in range(i0, min(i1, len(text))):
                    marks[i] = True
            base = (_is_bold(sp), _is_ital(sp))
            col = sp["color"]
            x0, x1 = sp["bbox"][0], sp["bbox"][2]
            i = 0
            while i < len(text):
                j = i
                while j < len(text) and marks[j] == marks[i]:
                    j += 1
                n = len(text)
                rect = pymupdf.Rect(x0 + (x1 - x0) * i / n, sp["bbox"][1], x0 + (x1 - x0) * j / n, sp["bbox"][3])
                add(text[i:j], (base[0], base[1], marks[i], col), rect)
                i = j
    return runs


def _near(c1: int, c2: int) -> bool:
    return max(abs(a - b) for a, b in zip(_rgb(c1), _rgb(c2))) < 0.25


def _markup(lines_spans: list[list[dict]], st: dict) -> tuple[str, str, list[dict], bool]:
    """(chữ thường, chữ kèm dấu <g1>…</g1> cho phần định dạng khác, mô tả từng dấu, cả đoạn có gạch dưới không)."""
    runs = _runs(lines_spans)
    plain = " ".join("".join(r[0] for r in runs).split())
    total = sum(len(r[0].strip()) for r in runs) or 1
    ul_all = sum(len(r[0].strip()) for r in runs if r[1] and r[1][2]) / total > 0.7
    main_col = max(lines_spans, key=len)[0]["color"] if lines_spans else 0
    cols: dict[int, int] = {}
    for r in runs:
        if r[1]:
            cols[r[1][3]] = cols.get(r[1][3], 0) + len(r[0].strip())
    if cols:
        main_col = max(cols, key=cols.get)
    out, marks = "", []
    for text, attrs, rect in runs:
        core = text.strip()
        diff = {}
        if attrs and core and len(_LETTERS.findall(core)) + sum(ch.isdigit() for ch in core) > 0:
            if attrs[0] != st["bold"]:
                diff["bold"] = attrs[0]
            if attrs[1] != st["italic"]:
                diff["italic"] = attrs[1]
            if attrs[2] != ul_all:
                diff["underline"] = attrs[2]
            if not _near(attrs[3], main_col):
                diff["color"] = _rgb(attrs[3])
        if not diff or len(marks) >= 30:
            out += text
            continue
        lead = text[:len(text) - len(text.lstrip())]
        trail = text[len(text.rstrip()):]
        marks.append({**diff, "rect": rect, "src": core})
        out += f"{lead}<g{len(marks)}>{core}</g{len(marks)}>{trail}"
    out = " ".join(out.split())
    if not marks:
        return plain, plain, [], ul_all
    return plain, out, marks, ul_all


def split_marks(text: str, n: int) -> list[tuple[str, int]] | None:
    """Tách bản dịch thành [(chữ, số dấu hoặc 0)]. None nếu máy dịch làm hỏng các dấu (khi đó bỏ định dạng trong dòng)."""
    parts: list[tuple[str, int]] = []
    pos, cur, seen = 0, 0, set()
    for m in _TAG.finditer(text):
        seg = text[pos:m.start()]
        if seg:
            parts.append((seg, cur))
        pos = m.end()
        k = int(m.group(2))
        if m.group(1):
            if cur != k:
                return None
            cur = 0
        else:
            if cur or k < 1 or k > n or k in seen:
                return None
            cur = k
            seen.add(k)
    if cur:
        return None
    if text[pos:]:
        parts.append((text[pos:], 0))
    return parts


def page_units(page) -> tuple[list[dict], int]:
    """Các đơn vị chữ cần dịch trên trang. Trả về (danh sách, số dòng bỏ qua vì chữ xoay nghiêng)."""
    d = tools.text_dict(page)
    units: list[dict] = []
    skipped = 0
    all_x0 = sorted(ln["bbox"][0] for b in d.get("blocks", []) for ln in b.get("lines", []))
    left_margin = all_x0[len(all_x0) // 20] if all_x0 else 0.0
    ub = page.rect * page.derotation_matrix
    ub.normalize()
    page_cx = (ub.x0 + ub.x1) / 2
    all_x1 = [ln["bbox"][2] for b in d.get("blocks", []) for ln in b.get("lines", [])]
    # chữ dịch dài hơn chỉ được nới tới lề phải thực tế của trang (không tràn ra ngoài vùng chữ gốc)
    right_limit = min(ub.x1 - 10, max(all_x1) + 1) if all_x1 else ub.x1 - 10
    ulines = _underlines(page)
    for b in d.get("blocks", []):
        lines = []
        for ln in b.get("lines", []):
            dx, dy = ln.get("dir", (1, 0))
            if not any(sp["text"].strip() for sp in ln["spans"]):
                continue
            if all(sp.get("alpha", 255) == 0 for sp in ln["spans"] if sp["text"].strip()):
                continue        # lớp chữ ẩn của bản scan đã OCR: chữ thật nằm trong ảnh, phải dịch theo kiểu "chữ trong hình"
            if abs(dy) > 0.01 or dx <= 0:
                skipped += 1
                continue
            lines.append(ln)
        if not lines:
            continue
        ul_used = _mark_underlines(lines, ulines)
        bbox = pymupdf.Rect(lines[0]["bbox"])
        for ln in lines[1:]:
            bbox |= pymupdf.Rect(ln["bbox"])
        single_seg = all(len(_segments(ln)) == 1 for ln in lines)
        widths = [ln["bbox"][2] - ln["bbox"][0] for ln in lines]
        leaders = sum(1 for ln in lines if _LEADER.match(_join([sp for sp in ln["spans"] if sp["text"].strip()])))
        wraps = len(lines) >= 2 and single_seg and bbox.width > 60 and leaders == 0 and \
            sum(1 for w in widths[:-1] if w >= 0.72 * bbox.width) >= max(1, (len(lines) - 1) * 0.6)
        if wraps:   # đoạn văn nhiều dòng: dịch cả đoạn cho đúng ngữ cảnh
            spans = [sp for ln in lines for sp in ln["spans"] if sp["text"].strip()]
            st = _style(spans)
            plain, text, marks, ul_all = _markup([[sp for sp in ln["spans"] if sp["text"].strip()] for ln in lines], st)
            if not translatable(plain):
                continue
            bases = [ln["spans"][0]["origin"][1] for ln in lines]
            lh = (bases[-1] - bases[0]) / (len(bases) - 1) / st["size"] if len(bases) > 1 else 1.2
            lefts = [ln["bbox"][0] for ln in lines]
            rights = [ln["bbox"][2] for ln in lines]
            centers = [(a + c) / 2 for a, c in zip(lefts, rights)]
            if max(centers) - min(centers) < 3 and max(lefts) - min(lefts) > 6:
                align = "center"
            elif max(rights) - min(rights) < 2.5 and max(lefts) - min(lefts) > 6:
                align = "right"
            elif max(rights[:-1]) - min(rights[:-1]) < 2.5 and len(lines) > 2:
                align = "justify"
            else:
                align = "left"
            units.append({"kind": "para", "text": text, "plain": plain, "marks": marks, "underline": ul_all,
                          "ul_rects": ul_used, "rect": bbox, "align": align, "lh": min(1.9, max(1.0, lh)),
                          "bands": [(pymupdf.Rect(ln["bbox"]), ln["spans"][0]["origin"][1], st["size"]) for ln in lines],
                          **st})
            continue
        for ln in lines:
            segs = _segments(ln)
            for k, seg in enumerate(segs):
                text = _join(seg)
                r = pymupdf.Rect(seg[0]["bbox"])
                for sp in seg[1:]:
                    r |= pymupdf.Rect(sp["bbox"])
                limit = (segs[k + 1][0]["bbox"][0] - 3) if k + 1 < len(segs) else right_limit
                st = _style(seg)
                base = seg[0]["origin"][1]
                plain, tagged, marks, ul_all = _markup([seg], st)
                mine = [u for u in ul_used if u.x1 > r.x0 - 1 and u.x0 < r.x1 + 1 and abs((u.y0 + u.y1) / 2 - base) < st["size"]]
                unit = {"kind": "line", "rect": r, "limit": max(limit, r.x1), "base": base, "align": "left",
                        "plain": plain, "marks": [], "underline": ul_all, "ul_rects": mine, **st}
                m = _LEADER.match(text)
                if m and translatable(m.group("title")):   # dòng mục lục: "Tiêu đề ....... 12"
                    unit.update(text=m.group("title").strip(), leader=True, ref=(m.group("ref") or ""),
                                bands=[(r, base, st["size"])])
                    units.append(unit)
                    continue
                if not translatable(text):
                    continue
                cx = (r.x0 + r.x1) / 2
                if len(segs) == 1 and abs(cx - page_cx) < 4 and r.x0 - left_margin > 15:
                    unit["align"] = "center"
                unit.update(text=tagged, marks=marks, bands=[(r, base, st["size"])])
                units.append(unit)
    return units, skipped


# =============================================================== chữ nằm trong hình ảnh
def _box_colors(pix, x0: float, y0: float, x1: float, y1: float) -> tuple[tuple, tuple]:
    """(màu nền, màu chữ) của một dòng chữ trong ảnh: nền = màu phổ biến nhất, chữ = màu khác nền nhất."""
    x0, y0 = max(0, int(x0)), max(0, int(y0))
    x1, y1 = min(pix.width - 1, int(x1)), min(pix.height - 1, int(y1))
    if x1 <= x0 or y1 <= y0:
        return (1, 1, 1), (0, 0, 0)
    cols = []
    nx, ny = min(40, x1 - x0 + 1), min(9, y1 - y0 + 1)
    for j in range(ny):
        y = y0 + (y1 - y0) * j // max(1, ny - 1)
        for i in range(nx):
            cols.append(tuple(pix.pixel(x0 + (x1 - x0) * i // max(1, nx - 1), y)[:3]))
    count: dict[tuple, list] = {}
    for c in cols:
        count.setdefault((c[0] >> 4, c[1] >> 4, c[2] >> 4), []).append(c)
    grp = max(count.values(), key=len)
    bg = tuple(sum(c[k] for c in grp) / len(grp) for k in range(3))
    far = sorted(cols, key=lambda c: -sum(abs(c[k] - bg[k]) for k in range(3)))[:max(3, len(cols) // 25)]
    fg = tuple(sum(c[k] for c in far) / len(far) for k in range(3))
    if sum(abs(fg[k] - bg[k]) for k in range(3)) < 90:      # không đủ tương phản: chọn đen/trắng theo nền
        fg = (0, 0, 0) if sum(bg) / 3 > 128 else (255, 255, 255)
    return tuple(v / 255 for v in bg), tuple(v / 255 for v in fg)


def page_images(page):
    """Các hình đủ lớn để có chữ trên trang: (khung trên trang, hệ số phóng, ảnh đã dựng, khoá nhận diện nội dung)."""
    import hashlib
    if page.rotation:
        return
    try:
        infos = page.get_image_info(hashes=True, xrefs=True)
    except Exception:
        infos = []
    try:
        visible = sum(len(sp["text"].strip()) for b in tools.text_dict(page).get("blocks", []) for ln in b.get("lines", [])
                      for sp in ln["spans"] if sp.get("alpha", 255) != 0)
    except Exception:
        visible = 0
    if visible < 80:
        # Trang gần như không có chữ thật: bản scan (kể cả scan bị cắt thành nhiều mảnh ảnh) hoặc chữ đã bị đổi thành
        # nét vẽ. Đọc CẢ TRANG như một hình duy nhất thay vì dò từng mảnh ảnh.
        z = 200 / 72
        while page.rect.width * z * page.rect.height * z > 6_000_000 and z > 1.0:
            z *= 0.9
        pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z), alpha=False)
        try:
            blank = pix.is_unicolor
        except Exception:
            blank = False
        if not blank:
            yield pymupdf.Rect(page.rect), z, pix, "page_" + hashlib.md5(pix.samples).hexdigest()
        return
    for info in infos:
        bbox = pymupdf.Rect(info["bbox"]) & page.rect
        if bbox.is_empty or bbox.width < 40 or bbox.height < 18:
            continue
        z = min(4.0, max(1.5, info.get("width", 0) / bbox.width))
        while bbox.width * z * bbox.height * z > 6_000_000 and z > 1.0:
            z *= 0.8
        pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z), clip=bbox, alpha=False)
        try:
            if pix.is_unicolor:
                continue                      # hình một màu: chắc chắn không có chữ
        except Exception:
            pass
        dg = info.get("digest")              # cùng một hình đặt ở nhiều chỗ/nhiều trang thì chỉ phải đọc một lần
        key = (dg.hex() if isinstance(dg, (bytes, bytearray)) else hashlib.md5(pix.samples).hexdigest()) \
            + f"_{round(bbox.width)}x{round(bbox.height)}"
        yield bbox, z, pix, key


_WORD3 = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
_DOMAIN = re.compile(r"^\S+\.(com|net|org|vn|edu|gov|io|info)\S*$", re.I)
_MATH_WORDS = {"lim", "log", "loge", "sin", "cos", "tan", "cot", "sec", "csc", "exp", "max", "min", "and", "mod", "det", "sup",
               "inf", "sqrt", "frac", "sum", "int", "prod", "arg", "deg", "dim", "ker", "gcd", "lcm", "sinh", "cosh", "tanh",
               "arcsin", "arccos", "arctan", "mol", "aq", "var", "cov", "vec", "bar", "hat", "for", "với", "và"}


# từ nối đứng giữa các công thức ("x + y and y + x"): công thức giữ nguyên, riêng từ này vẫn phải dịch
_LINKS = {"and", "or", "where", "if", "then", "with", "for", "so", "hence", "thus", "when", "while", "but", "not", "is",
          "are", "as", "to", "from", "by", "of", "in", "on", "at", "that", "such", "all", "any", "some", "since", "because",
          "therefore", "implies", "iff", "otherwise", "else", "resp", "versus", "vs", "equals", "let", "given", "between",
          "et", "ou", "si", "donc", "avec", "pour", "und", "oder", "wenn", "dann", "mit", "für", "also", "con", "para",
          "entonces", "donde", "cuando"}


def _link_words(pix, px, text: str) -> list:
    """Từ nối nằm trong một dòng công thức: [(từ, x0, x1)] tính theo điểm ảnh của hình. Vị trí lấy từ chính nét mực
    trong ảnh (cụm nét có khoảng trống hai bên), nên chỉ trả về khi xác định được chắc chắn."""
    toks = text.split()
    hits = [k for k, t in enumerate(toks) if t.strip(".,;:").lower() in _LINKS and t.strip(".,;:").islower()]
    if not hits or len(toks) < 2 or len(hits) > 4:
        return []
    x0, y0 = max(0, int(px[0])), max(0, int(px[1]))
    x1, y1 = min(pix.width - 1, int(px[2])), min(pix.height - 1, int(px[3]))
    w, h = x1 - x0 + 1, y1 - y0 + 1
    if w < 20 or h < 6 or w * h > 400000:
        return []
    bg = [v * 255 for v in _box_colors(pix, x0, y0, x1, y1)[0]]
    step = max(1, h // 24)
    ink = []
    for x in range(x0, x1 + 1):
        on = False
        for y in range(y0, y1 + 1, step):
            c = pix.pixel(x, y)
            if abs(c[0] - bg[0]) + abs(c[1] - bg[1]) + abs(c[2] - bg[2]) > 150:
                on = True
                break
        ink.append(on)
    segs = []                       # các cụm nét mực liền nhau (khe hẹp giữa các chữ cái của một từ thì nối lại)
    start = None
    gap = 0
    join = max(2, int(0.16 * h))
    for i, on in enumerate(ink + [False] * (join + 1)):
        if on:
            if start is None:
                start = i
            gap = 0
        elif start is not None:
            gap += 1
            if gap > join:
                segs.append([start, i - gap])
                start = None
    if len(segs) < 2:
        return []
    out = []
    used = set()
    pos = 0
    spans = []
    for t in toks:
        spans.append((pos, pos + len(t)))
        pos += len(t) + 1
    total = max(1, pos - 1)
    for k in hits:
        word = toks[k].strip(".,;:")
        centre = (spans[k][0] + spans[k][1]) / 2 / total * w
        want = len(word) * 0.5 * h
        best = None
        for n, (a, b) in enumerate(segs):
            if n in used or not 0.5 * want <= b - a + 1 <= 1.8 * want or abs((a + b) / 2 - centre) > 0.22 * w:
                continue
            left = a - segs[n - 1][1] if n else w
            right = segs[n + 1][0] - b if n + 1 < len(segs) else w
            side = min(left, right)
            if side < 0.3 * h:
                continue                 # dính sát công thức bên cạnh: không chắc là từ nào, bỏ qua
            key = (-min(side, 2 * h) // max(1, h // 2), abs((a + b) / 2 - centre))
            if best is None or key < best[0]:
                best = (key, n)
        if best is not None:
            used.add(best[1])
            a, b = segs[best[1]]
            out.append((word, x0 + a, x0 + b + 1))
    return out


def prose_like(text: str) -> bool:
    """Dòng chữ trong ảnh có đáng dịch không: phải có lời văn, không phải công thức / ký hiệu / địa chỉ web.
    (Viết lại công thức toán, hoá bằng chữ thường sẽ làm hỏng ký hiệu, nên các dòng đó được giữ nguyên trong ảnh.)"""
    t = text.strip()
    if _DOMAIN.match(t) or _URLISH.match(t):
        return False
    words = []
    letters = 0
    for tok in t.split():
        core = re.sub(r"^\d+[.)]", "", tok).strip("()[]{}.,;:!?\"'“”‘’/-–—")      # "5.Functions" → "Functions"
        # từ của lời văn: toàn chữ cái, viết thường / Viết Hoa Đầu / VIẾT HOA. Loại: CH3COOH, NaOH, x₁, f(x), a^n, sqrt(ax...
        if core.isalpha() and (core.islower() or core.istitle() or core.isupper()) and core.lower() not in _MATH_WORDS:
            if len(core) >= 3:
                words.append(core)
            if len(core) >= 2:
                letters += len(core)             # từ ngắn (to, of, là, và...) cũng là lời văn
    solid = len(re.sub(r"\s", "", t)) or 1
    if len(words) >= 2:
        return letters >= 0.45 * solid      # phần lớn là ký hiệu, biến số, con số → công thức, giữ nguyên
    return len(words) == 1 and len(words[0]) >= 5 and len(words[0]) >= 0.6 * len(re.sub(r"[\s\d.]", "", t))


def _group_lines(rows: list[dict]) -> list[list[dict]]:
    """Gom các dòng liền nhau của cùng một đoạn văn (để dịch trọn câu, không dịch rời từng dòng)."""
    rows = sorted(rows, key=lambda r: (r["rect"].y0, r["rect"].x0))
    for row in rows:      # lề phải của cột chữ chứa dòng này = mép phải xa nhất của các dòng cùng lề trái
        r = row["rect"]
        col = [x["rect"] for x in rows if abs(x["rect"].x0 - r.x0) < 1.5 * r.height]
        row["right"] = max(c.x1 for c in col)
        row["colw"] = row["right"] - min(c.x0 for c in col)
    groups: list[list[dict]] = []
    for row in rows:
        r = row["rect"]
        best = None
        for g in groups:
            last = g[-1]["rect"]
            h = (last.height + r.height) / 2
            same_size = 0.72 <= r.height / max(0.1, last.height) <= 1.4
            gap = r.y0 - last.y1
            left = min(x["rect"].x0 for x in g)
            aligned = abs(r.x0 - left) < 1.2 * h           # cùng lề trái (dòng đầu đoạn có thể thụt vào)
            # dòng trước phải chạy sát lề phải của cột thì câu mới còn tiếp ở dòng này (dòng cuối đoạn / ô bảng thì ngắn hơn)
            prev_full = last.x1 >= g[-1]["right"] - max(0.035 * g[-1]["colw"], 0.8 * h)
            if same_size and -0.4 * h <= gap < 0.75 * h and aligned and prev_full:
                best = g
        if best is not None:
            best.append(row)
        else:
            groups.append([row])
    return groups


def image_units(page, lines_for) -> list[dict]:
    """Chữ nằm trong các hình ảnh của trang (ảnh chụp màn hình, sơ đồ, trang scan...). Các dòng của cùng một đoạn văn
    được gom lại thành một đơn vị dịch; dòng chỉ có công thức/ký hiệu thì bỏ qua (giữ nguyên trong ảnh)."""
    try:      # chỉ tính chữ NHÌN THẤY được; lớp chữ ẩn do OCR tạo ra không phải là "trang đã có chữ thật"
        words = [pymupdf.Rect(sp["bbox"]) for b in tools.text_dict(page).get("blocks", []) for ln in b.get("lines", [])
                 for sp in ln["spans"] if sp["text"].strip() and sp.get("alpha", 255) != 0]
    except Exception:
        words = []
    units: list[dict] = []
    for bbox, z, pix, key in page_images(page):
        rows = []
        mine: list[dict] = []
        for (x0, y0, x1, y1), text in lines_for(pix, key):
            text = " ".join(str(text).split())
            if not text or y1 - y0 < 5 or x1 - x0 < 5:
                continue
            r = pymupdf.Rect(bbox.x0 + x0 / z, bbox.y0 + y0 / z, bbox.x0 + x1 / z, bbox.y0 + y1 / z) & bbox
            if r.is_empty or r.height < 2.5 or r.height > 2.2 * r.width and len(text) > 2:
                continue
            area = r.get_area() or 1
            if sum((w & r).get_area() for w in words if w.intersects(r)) > 0.3 * area:
                continue                      # chỗ này trang đã có chữ thật (được dịch theo cách thường)
            rows.append({"rect": r, "px": (x0, y0, x1, y1), "text": text})
        for g in _group_lines(rows):
            text = ""
            for row in g:
                if text.endswith("-") and row["text"][:1].islower():
                    text = text[:-1] + row["text"]        # từ bị ngắt cuối dòng: "expres-" + "sions"
                else:
                    text = (text + " " + row["text"]).strip()
            if not translatable(text) or not prose_like(text):
                for row in g:                         # dòng công thức: chỉ dịch từ nối đứng giữa các công thức
                    if prose_like(row["text"]):
                        continue
                    for word, wx0, wx1 in _link_words(pix, row["px"], row["text"]):
                        r = row["rect"]
                        wr = pymupdf.Rect(bbox.x0 + wx0 / z - 1, r.y0, bbox.x0 + wx1 / z + 1, r.y1)
                        bgc, fgc = _box_colors(pix, wx0, row["px"][1], wx1, row["px"][3])
                        mine.append({"kind": "img", "text": word, "plain": word, "marks": [], "underline": False,
                                     "ul_rects": [], "bands": [], "rect": wr, "bg": bgc, "color": fgc,
                                     "size": max(3.0, min(r.height * 0.72, 40)), "font": "Arial", "flags": 0,
                                     "bold": False, "italic": False, "align": "center", "lines": [(pymupdf.Rect(wr), bgc)],
                                     "room_y": r.y1 + 1, "link": True})
                continue
            cols = [_box_colors(pix, *row["px"]) for row in g]
            hs = sorted(row["rect"].height for row in g)
            size = max(3.0, min(hs[len(hs) // 2] * 0.72, 40))
            rect = pymupdf.Rect(g[0]["rect"])
            for row in g[1:]:
                rect |= row["rect"]
            unit = {"kind": "img", "text": text, "plain": text, "marks": [], "underline": False, "ul_rects": [],
                    "bands": [], "rect": rect, "bg": cols[0][0], "color": cols[0][1], "size": size,
                    "font": "Arial", "flags": 0, "bold": False, "italic": False, "align": "left",
                    "lines": [(pymupdf.Rect(row["rect"]), c[0]) for row, c in zip(g, cols)]}
            below = [o["rect"].y0 for o in rows if o not in g and o["rect"].y0 >= rect.y1 - 1
                     and o["rect"].x1 > rect.x0 and o["rect"].x0 < rect.x1]
            unit["room_y"] = min(below + [bbox.y1]) - 1.5      # không lấn sang dòng chữ / công thức nằm ngay bên dưới
            if len(g) > 1:
                pitch = (g[-1]["rect"].y0 - g[0]["rect"].y0) / (len(g) - 1)
                unit["lh"] = min(1.9, max(1.0, pitch / size))
            mine.append(unit)
        if len(mine) >= 3:      # khung OCR cao thấp lệch nhau vài điểm ảnh: đưa các dòng cùng cỡ về MỘT cỡ chữ cho đều mắt
            sizes = sorted(u["size"] for u in mine)
            med = sizes[len(sizes) // 2]
            for u in mine:
                if 0.78 * med <= u["size"] <= 1.28 * med:
                    if "lh" in u:
                        u["lh"] = min(1.9, max(1.0, u["lh"] * u["size"] / med))
                    u["size"] = med
        links = [u for u in mine if u.get("link")]
        if links:                # từ nối giữa công thức: cùng một cỡ chữ với lời văn của trang
            pool = sorted(u["size"] for u in mine if not u.get("link")) or sorted(u["size"] for u in links)
            for u in links:
                u["size"] = pool[len(pool) // 2]
        units += mine
    return units


def read_images(doc, pages: list[int], reader, store=None, progress=None) -> dict:
    """Đọc chữ của mọi hình trong các trang. Hình trùng nhau chỉ đọc một lần; kết quả cũ lấy lại từ bộ nhớ (store).
    Trả về {khoá hình: các dòng chữ}."""
    kind = getattr(reader, "__name__", "ocr")
    found: dict = {}
    pending: list = []
    many = getattr(reader, "many", None)

    def flush():
        if not pending:
            return
        res = many([item for _k, item in pending])
        for (k, _item), lines in zip(pending, res):
            found[k] = lines
            if store is not None:
                store.ocr_put(kind, k, lines)
        pending.clear()
    for n, i in enumerate(pages):
        for _bbox, _z, pix, key in page_images(doc[i]):
            if key in found or any(key == k for k, _ in pending):
                continue
            old = store.ocr_get(kind, key) if store is not None else None
            if old is not None:
                found[key] = old
            elif many:
                pending.append((key, reader.pack(pix)))
                if len(pending) >= getattr(reader, "batch", 4):
                    flush()
            else:
                found[key] = reader(pix)
                if store is not None:
                    store.ocr_put(kind, key, found[key])
        if progress:
            progress(n + 1, len(pages))
    flush()
    return found


# =============================================================== ghép chữ đã dịch
_archives: dict[str, pymupdf.Archive] = {}


def _font_css(unit: dict, text: str) -> tuple[str, pymupdf.Archive | None, pymupdf.Font]:
    font, path = tools.pick_font_file(unit["font"], unit["flags"], text, bold=unit["bold"], italic=unit["italic"])
    if path:
        d = os.path.dirname(path)
        if d not in _archives:
            _archives[d] = pymupdf.Archive(d)
        face = f'@font-face {{font-family: tf; src: url("{os.path.basename(path)}");}}'
        return face + " * {font-family: tf;}", _archives[d], font
    name = unit["font"].lower()
    generic = "monospace" if unit["flags"] & 8 or "mono" in name or "courier" in name else \
        "serif" if unit["flags"] & 4 else "sans-serif"
    extra = ("font-weight: bold;" if unit["bold"] else "") + ("font-style: italic;" if unit["italic"] else "")
    return f"* {{font-family: {generic}; {extra}}}", None, font


def _faces_css(unit: dict, text: str, combos: set) -> tuple[str, pymupdf.Archive | None, pymupdf.Font | None]:
    """CSS phông cho đoạn có nhiều kiểu chữ (thường/đậm/nghiêng) trong cùng một dòng."""
    faces, dirs, main_font = [], [], None
    for bold, ital in sorted(combos):
        font, path = tools.pick_font_file(unit["font"], unit["flags"], text, bold=bold, italic=ital)
        if not path:
            return _generic_css(unit), None, None
        if (bold, ital) == (unit["bold"], unit["italic"]):
            main_font = font
        dirs.append(os.path.dirname(path))
        faces.append('@font-face {font-family: tf; font-weight: %s; font-style: %s; src: url("%s");}'
                     % ("bold" if bold else "normal", "italic" if ital else "normal", os.path.basename(path)))
    key = "|".join(sorted(set(dirs)))
    if key not in _archives:
        arch = pymupdf.Archive(dirs[0])
        for d in sorted(set(dirs[1:]) - {dirs[0]}):
            arch.add(d)
        _archives[key] = arch
    return " ".join(faces) + " * {font-family: tf;}", _archives[key], main_font


def _generic_css(unit: dict) -> str:
    name = unit["font"].lower()
    generic = "monospace" if unit["flags"] & 8 or "mono" in name or "courier" in name else \
        "serif" if unit["flags"] & 4 else "sans-serif"
    return f"* {{font-family: {generic};}}"


def _body_html(text: str, unit: dict, parts) -> str:
    if not parts:
        return html.escape(text)
    out = ""
    for seg, k in parts:
        if not k:
            out += html.escape(seg)
            continue
        mk = unit["marks"][k - 1]
        css = ""
        if "bold" in mk:
            css += "font-weight:%s;" % ("bold" if mk["bold"] else "normal")
        if "italic" in mk:
            css += "font-style:%s;" % ("italic" if mk["italic"] else "normal")
        if "underline" in mk:
            css += "text-decoration:%s;" % ("underline" if mk["underline"] else "none")
        if "color" in mk:
            css += "color:rgb(%d,%d,%d);" % tuple(int(round(c * 255)) for c in mk["color"])
        lead = seg[:len(seg) - len(seg.lstrip())]
        trail = seg[len(seg.rstrip()):]
        out += f'{html.escape(lead)}<span style="{css}">{html.escape(seg.strip())}</span>{html.escape(trail)}'
    return out


def apply_page(page, units: list[dict], translations: list[str]) -> int:
    """Xoá chữ gốc của các đơn vị đã dịch và viết bản dịch vào đúng chỗ. Trả về số đơn vị đã thay."""
    todo = [(u, t.strip()) for u, t in zip(units, translations)
            if t and t.strip() and t.strip() != u["text"].strip()]
    if not todo:
        return 0
    try:
        links = page.get_links()
    except Exception:
        links = []
    for u, _t in todo:
        for r, base, size in u["bands"]:
            band = pymupdf.Rect(r.x0 + 0.3, base - 0.45 * size, r.x1 - 0.3, base - 0.15 * size)
            if band.is_empty or band.width < 1:
                band = r + (0.3, 0.3, -0.3, -0.3)
            page.add_redact_annot(band, fill=False, cross_out=False)
        for ur in u.get("ul_rects", []):   # nét gạch dưới cũ nằm sai chỗ so với chữ đã dịch: xoá, lát vẽ lại theo chữ mới
            page.add_redact_annot(pymupdf.Rect(ur.x0 - 0.4, ur.y0 - 0.5, ur.x1 + 0.4, ur.y1 + 0.5), fill=False, cross_out=False)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
                          text=pymupdf.PDF_REDACT_TEXT_REMOVE)
    moves: list[tuple[pymupdf.Rect, str, pymupdf.Rect]] = []   # (khung cũ của chữ có liên kết, chữ mới, vùng tìm)
    rot = page.rotation
    done = 0
    for u, t in todo:
        size = u["size"]
        col = "rgb(%d,%d,%d)" % tuple(int(round(c * 255)) for c in u["color"])
        marks = u.get("marks") or []
        parts = split_marks(t, len(marks)) if marks and not u.get("leader") else None
        if parts is not None and not any(k for _s, k in parts):
            parts = None
        t = strip_marks(t)
        combos = {(u["bold"], u["italic"])}
        for _s, k in parts or []:
            if k:
                mk = marks[k - 1]
                combos.add((mk.get("bold", u["bold"]), mk.get("italic", u["italic"])))
        try:
            face, arch, font = _font_css(u, t) if len(combos) == 1 else _faces_css(u, t, combos)
        except Exception:
            face, arch, font = "* {font-family: sans-serif;}", None, None
        deco = ("font-weight:%s; font-style:%s; " % ("bold" if u["bold"] else "normal", "italic" if u["italic"] else "normal")
                if len(combos) > 1 else "") + ("text-decoration:underline; " if u.get("underline") else "")
        if u["kind"] == "img":   # chữ trong hình: phủ màu nền lên (các) dòng chữ cũ rồi viết bản dịch đè lên
            r = pymupdf.Rect(u["rect"])
            rows = u.get("lines") or [(r, u["bg"])]
            for lr, bg in rows:
                try:
                    page.draw_rect(lr + (-0.6, -0.4, 0.6, 0.4), color=None, fill=bg, width=0)
                except Exception:
                    pass
            room = max(r.y1, min(u.get("room_y", r.y1), r.y1 + 6 * size))
            wrap_css = face + f" p {{font-size:{size:.2f}px; color:{col}; line-height:{u.get('lh', 1.2):.2f}; margin:0; " \
                              f"padding:0; text-align:{'justify' if len(rows) > 2 else 'left'};}}"
            line_css = face + f" p {{font-size:{size:.2f}px; color:{col}; line-height:1.1; margin:0; padding:0; white-space:nowrap;}}"
            body = f"<p>{html.escape(t)}</p>"
            box = pymupdf.Rect(r.x0, r.y0 - 0.1 * size, r.x1 + 0.6, r.y1 + 0.3 * size)
            tall = pymupdf.Rect(box.x0, box.y0, box.x1, max(box.y1, room))
            line = pymupdf.Rect(r.x0, r.y0 - 0.15 * r.height, r.x1 + 0.6, r.y1 + 0.2 * r.height)
            if u.get("link"):         # từ nối giữa hai công thức: viết giữa chỗ cũ, không xuống dòng
                line_css = line_css.replace("white-space:nowrap;", "white-space:nowrap; text-align:center;")
                line = pymupdf.Rect(line.x0 - 0.25 * r.height, line.y0, line.x1 + 0.25 * r.height, line.y1)
            # thử lần lượt: vừa khung gốc → xuống dòng vào chỗ trống bên dưới → cùng lắm mới thu nhỏ hẳn
            tries = [(box, wrap_css, 0.72), (tall, wrap_css, 0.6), (tall, wrap_css, 0)] if len(rows) > 1 else \
                    [(line, line_css, 0.72), (tall, wrap_css, 0.62), (line, line_css, 0)]
            if u.get("link"):
                tries = [(line, line_css, 0.6), (line, line_css, 0)]
            ok = False
            for rect, css, low in tries:
                try:
                    spare, _sc = page.insert_htmlbox(rect, body, css=css, archive=arch, scale_low=low, rotate=rot)
                except Exception:
                    spare = -1
                if spare >= 0:
                    ok = True
                    break
            done += 1 if ok else 0
            continue
        elif u["kind"] == "para":
            r = pymupdf.Rect(u["rect"])
            rect = pymupdf.Rect(r.x0 - 0.5, r.y0 - 0.12 * size, r.x1 + 1.0, r.y1 + 0.25 * size)
            css = face + f" p {{font-size:{size:.2f}px; color:{col}; line-height:{u['lh']:.2f}; margin:0; padding:0; " \
                         f"{deco}text-align:{u['align']};}}"
            body = f"<p>{_body_html(t, u, parts)}</p>"
            low = 0.45
        else:
            r = u["rect"]
            text = t
            if u.get("leader"):   # dựng lại hàng chấm dẫn cho vừa tới số trang
                ref = u.get("ref", "")
                width = r.width
                if font is not None:
                    try:
                        used = font.text_length(t + " ", size) + font.text_length(" " + ref, size)
                        dotw = font.text_length(".", size) or 1
                        k = int(max(0, width - used) / dotw)
                        text = t + " " + "." * max(3, k) + (" " + ref if ref else "")
                    except Exception:
                        text = t + " ..... " + ref
                else:
                    text = t + " ..... " + ref
                rect = pymupdf.Rect(r.x0, r.y0 - 0.12 * size, r.x1 + 0.5, r.y1 + 0.3 * size)
                align = "left"
            elif u["align"] == "center":
                ub = page.rect * page.derotation_matrix
                ub.normalize()
                cx = (r.x0 + r.x1) / 2
                half = max(r.width / 2, min(cx - ub.x0 - 10, ub.x1 - 10 - cx))
                rect = pymupdf.Rect(cx - half, r.y0 - 0.12 * size, cx + half, r.y1 + 0.3 * size)
                align = "center"
            else:
                rect = pymupdf.Rect(r.x0, r.y0 - 0.12 * size, max(u["limit"], r.x1) + 0.5, r.y1 + 0.3 * size)
                align = "left"
            css = face + f" p {{font-size:{size:.2f}px; color:{col}; line-height:1.15; margin:0; padding:0; " \
                         f"{deco}white-space:nowrap; text-align:{align};}}"
            body = f"<p>{_body_html(text, u, parts if text == t else None)}</p>"
            low = 0
        try:
            spare, _scale = page.insert_htmlbox(rect, body, css=css, archive=arch, scale_low=low, rotate=rot)
            if spare < 0:   # không vừa ở mức thu nhỏ cho phép: thu nhỏ tiếp để không tràn ra ngoài khung
                page.insert_htmlbox(rect, body, css=css, archive=arch, scale_low=0, rotate=rot)
            done += 1
            for seg, k in parts or []:
                if k and marks[k - 1].get("rect") is not None and seg.strip():
                    moves.append((marks[k - 1]["rect"], seg.strip(), pymupdf.Rect(rect)))
        except Exception:
            try:
                page.insert_htmlbox(rect, body, css=f"p {{font-size:{size:.2f}px; color:{col}; margin:0;}}",
                                    scale_low=0, rotate=rot)
                done += 1
            except Exception:
                pass
    try:   # việc xoá chữ có thể làm mất liên kết nằm đè lên chữ: gắn lại
        left = {(round(l["from"].x0), round(l["from"].y0), l.get("uri"), l.get("page")) for l in page.get_links()}
        for l in links:
            key = (round(l["from"].x0), round(l["from"].y0), l.get("uri"), l.get("page"))
            if key not in left and l.get("kind") in (pymupdf.LINK_URI, pymupdf.LINK_GOTO):
                page.insert_link({k: v for k, v in l.items() if k in ("kind", "from", "uri", "page", "to", "zoom")})
    except Exception:
        pass
    try:   # liên kết nằm trên cụm chữ có định dạng riêng: dời vùng bấm sang đúng chỗ của cụm chữ đã dịch
        if moves and links:
            page = page.parent.reload_page(page)   # nạp lại trang thì mới thấy các liên kết vừa gắn lại
            for l in page.get_links():
                fr = pymupdf.Rect(l["from"])
                for old, seg, clip in moves:
                    inter = fr & old
                    if inter.is_empty or inter.get_area() < 0.5 * min(fr.get_area(), old.get_area()):
                        continue
                    hits = page.search_for(seg, clip=clip + (-2, -2, 2, 2))
                    if hits:
                        new = pymupdf.Rect(hits[0])
                        for h in hits[1:]:
                            if abs(h.y0 - hits[0].y0) < 2:
                                new |= h
                        l["from"] = new
                        page.update_link(l)
                    break
    except Exception:
        pass
    return done


# =============================================================== bộ máy dịch
_net = {"direct": False}   # True: lần trước đi qua proxy của máy không được, đi thẳng thì được


def system_proxy() -> str:
    try:
        px = urllib.request.getproxies()
        return px.get("https") or px.get("http") or ""
    except Exception:
        return ""


def _open(req, timeout: float, direct: bool):
    if direct:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        return opener.open(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout)


def _http(url: str, data: bytes | None = None, headers: dict | None = None, timeout: float = 120) -> bytes:
    req = urllib.request.Request(url, data=data, headers=headers or {})
    local = "://localhost" in url or "://127.0.0.1" in url
    modes = [True] if (_net["direct"] or local) else ([False, True] if system_proxy() else [False])
    last: Exception | None = None
    for direct in modes:
        try:
            with _open(req, timeout, direct) as r:
                out = r.read()
            if direct and not local:
                _net["direct"] = True
            return out
        except urllib.error.HTTPError:
            raise
        except urllib.error.URLError as e:
            last = e
        except OSError as e:   # hết thời gian chờ khi đang đọc dữ liệu, mất kết nối giữa chừng...
            last = urllib.error.URLError(f"hết thời gian chờ hoặc mất kết nối ({e})")
    raise last if last else urllib.error.URLError("không rõ lỗi mạng")


def is_timeout(e: Exception) -> bool:
    t = str(getattr(e, "reason", e)).lower()
    return "timed out" in t or "timeout" in t or "hết thời gian" in t


def _http_error_text(e: urllib.error.HTTPError) -> str:
    try:
        body = e.read().decode("utf-8", "ignore")
        try:
            j = json.loads(body)
            return str((j.get("error") or {}).get("message") or body)[:400]
        except Exception:
            return body[:400]
    except Exception:
        return str(e)


def _batches(texts: list[str], max_items: int, max_chars: int) -> list[list[int]]:
    out, cur, size = [], [], 0
    for i, t in enumerate(texts):
        if cur and (len(cur) >= max_items or size + len(t) > max_chars):
            out.append(cur)
            cur, size = [], 0
        cur.append(i)
        size += len(t)
    if cur:
        out.append(cur)
    return out


class Engine:
    """Lớp gốc: dịch danh sách chuỗi, có tiến độ và cho phép dừng giữa chừng."""
    name = "?"
    batch_items, batch_chars = 40, 6000

    def __init__(self):
        self.cancel = False

    def _check(self):
        if self.cancel:
            raise Cancelled()

    def _sleep(self, seconds: float, note=None):
        end = time.time() + seconds
        while time.time() < end:
            self._check()
            if note:
                note(max(0, int(end - time.time())))
            time.sleep(0.25)

    def translate_many(self, texts: list[str], target: str, source: str = "", progress=None, **opts) -> list[str]:
        out = list(texts)
        cache: dict[str, str] = {}
        idx = [i for i, t in enumerate(texts) if t.strip()]
        uniq: list[str] = []
        for i in idx:   # câu trùng nhau (header/footer lặp lại) chỉ dịch một lần để nhất quán và đỡ tốn lượt gọi
            if texts[i] not in cache:
                cache[texts[i]] = ""
                uniq.append(texts[i])
        done = 0
        for batch in _batches(uniq, self.batch_items, self.batch_chars):
            self._check()
            src = [uniq[i] for i in batch]
            res = self._translate_checked(src, target, source, progress, **opts)
            for s, r in zip(src, res):
                cache[s] = r
            done += len(batch)
            if progress:
                progress(done, len(uniq), "")
        for i in idx:
            out[i] = cache.get(texts[i]) or texts[i]
        return out

    def _translate_checked(self, src: list[str], target, source, progress, **opts) -> list[str]:
        try:
            res = self.translate_batch(src, target, source, progress=progress, **opts)
        except TooSlow:
            if len(src) < 2:
                raise
            mid = len(src) // 2
            return self._translate_checked(src[:mid], target, source, progress, **opts) + \
                self._translate_checked(src[mid:], target, source, progress, **opts)
        if len(res) == len(src):
            return res
        if len(src) == 1:
            return [res[0] if res else src[0]]
        mid = len(src) // 2   # bộ máy trả sai số câu: chia đôi rồi dịch lại
        return self._translate_checked(src[:mid], target, source, progress, **opts) + \
            self._translate_checked(src[mid:], target, source, progress, **opts)

    def translate_batch(self, src: list[str], target: str, source: str, progress=None, **opts) -> list[str]:
        raise NotImplementedError


def build_prompt(target: str, source: str, domain: str, glossary: str, context: str) -> str:
    _code, tname = lang_name(target)
    sname = lang_name(source)[1] if source else "the source language (detect it automatically)"
    dom = next((en for key, _vi, en in DOMAINS if key == domain), "general documents")
    p = (f"You are a senior professional translator specialising in {dom}. Translate from {sname} into {tname}.\n"
         "The user message is a JSON array of text fragments taken from ONE document in reading order.\n"
         "Return ONLY a JSON array of strings with exactly the same number of items in the same order; "
         "item i is the translation of fragment i.\n"
         "Rules:\n"
         f"- Translate the meaning accurately and naturally, as a native {tname} specialist would write it; use the "
         f"standard terminology of {dom} in {tname}, and keep each term translated the same way everywhere.\n"
         "- Use the surrounding fragments as context: fragments may be headings, table cells, list items, headers, "
         "footers or parts of one sentence.\n"
         "- Keep unchanged: numbers, dates, amounts, units, codes, article/clause numbers, URLs, e-mail addresses, "
         "file names, product and brand names, personal and company names (do not translate or transliterate them "
         "unless an official name exists).\n"
         "- Keep every mathematical, chemical or physical formula, equation, symbol, variable and unit exactly as written "
         "in the source (e.g. f(x), x₁, ∂f/∂x, √(ax+b), H₂SO₄, FX̅): never translate, spell out, re-order or reformat them; "
         "translate only the surrounding words. A fragment that is only a formula is returned unchanged.\n"
         "- Keep leading numbering and bullets (e.g. '1.2', 'a)', '-', 'Điều 3.') and the trailing punctuation.\n"
         "- Do not add explanations, notes, quotes or line breaks. Do not merge or split fragments.\n"
         "- Some fragments contain inline formatting markers such as <g1>...</g1>, <g2>...</g2> (bold, underlined or "
         "linked words). Keep every marker pair exactly once and unchanged, and put it around the translated words "
         "that correspond to the marked source words. Never translate, drop, add or nest markers.\n"
         f"- If a fragment is already in {tname} or must not be translated, return it unchanged.")
    if glossary.strip():
        p += "\nMandatory glossary (source = required translation), apply it consistently:\n" + glossary.strip()[:4000]
    if context.strip():
        p += "\n\nDocument excerpt for context only (do NOT translate or return it):\n" + context.strip()[:1500]
    return p


def _parse_array(text: str, n: int) -> list[str]:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", t).strip()
    try:
        j = json.loads(t)
    except Exception:
        m = re.search(r"\[.*\]", t, re.S)
        if not m:
            raise TranslateError("Bộ máy dịch trả về dữ liệu không đúng định dạng.")
        j = json.loads(m.group(0))
    if isinstance(j, dict):
        j = next((v for v in j.values() if isinstance(v, list)), [])
    return [str(x) if not isinstance(x, str) else x for x in j]


GEMINI_FALLBACKS = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite",
                    "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]


class GeminiEngine(Engine):
    name = "Gemini (Google AI)"
    base = "https://generativelanguage.googleapis.com/v1beta"
    batch_items, batch_chars = 140, 14000   # gói miễn phí giới hạn số LƯỢT gọi mỗi phút: gom nhiều đoạn vào một lượt

    def __init__(self, api_key: str, model: str = "", quick: bool = False, prefer: str = "", fast: bool = False):
        super().__init__()
        self.key = api_key.strip()
        self.fixed = model.strip()      # model người dùng tự gõ (nếu có) thì không tự đổi sang model khác
        self.model = self.fixed
        self.quick = quick              # chế độ kiểm tra key: không chờ lâu, không thử lại nhiều lần
        self.prefer = prefer.strip()    # model đã kiểm tra là chạy được với key này: thử nó trước tiên
        self.timeout = 25 if quick else 150
        self.fast = fast                # cho phép dùng tạm model khác khi model chính hết lượt
        self._cool: dict[str, float] = {}   # model -> thời điểm dùng lại được
        self.used: set[str] = set()
        self.main = ""                  # model chính: model đầu tiên dịch được với key này
        self._cands: list[str] | None = None
        self._bad: dict[str, str] = {}  # model không dùng được với key này -> lý do
        self.use_schema = True
        self.use_thinking_cfg = True    # yêu cầu model "nghĩ ít" cho nhanh; model nào không nhận thì bỏ
        self.listed = -1                # số model Google trả về khi hỏi danh sách (-1: chưa hỏi được)
        self.slow = 0
        if not self.key:
            raise TranslateError("Chưa nhập API key của Gemini.")

    def candidates(self) -> list[str]:
        """Các model sẽ thử lần lượt: Flash mới nhất trước, rồi Flash-Lite, rồi danh sách dự phòng."""
        if self.fixed:
            return [self.fixed]
        if self._cands is None:
            found: list[str] = []
            try:
                raw = _http(f"{self.base}/models?pageSize=200", headers={"x-goog-api-key": self.key},
                            timeout=LIST_TIMEOUT if self.quick else 40)
                names = [m["name"].split("/")[-1] for m in json.loads(raw).get("models", [])
                         if "generateContent" in m.get("supportedGenerationMethods", [])]
                bad = ("tts", "live", "image", "transcribe", "embedding", "omni", "vision", "audio", "computer",
                       "robotics", "learnlm", "gemma")

                def ver(n):
                    m = re.search(r"gemini-(\d+)(?:\.(\d+))?", n)
                    return (int(m.group(1)), int(m.group(2) or 0)) if m else (0, 0)
                flash = [n for n in names if n.startswith("gemini") and "flash" in n and not any(b in n for b in bad)]
                stable = [n for n in flash if "preview" not in n and "exp" not in n]
                main = sorted([n for n in stable if "lite" not in n], key=ver, reverse=True)
                lite = sorted([n for n in stable if "lite" in n], key=ver, reverse=True)
                rest = sorted([n for n in flash if n not in stable], key=ver, reverse=True)
                found = main + lite + rest
                self.listed = len(names)
            except urllib.error.HTTPError as e:
                if e.code in (400, 401, 403):
                    raise TranslateError("Google từ chối API key này: " + _http_error_text(e))
            except urllib.error.URLError as e:
                raise TranslateError(f"Không kết nối được tới máy chủ Gemini của Google. Kiểm tra mạng, tường lửa "
                                     f"hoặc proxy của công ty.\nChi tiết: {e.reason}")
            except Exception:
                pass
            for n in GEMINI_FALLBACKS:
                if n not in found:
                    found.append(n)
            if self.prefer:
                found = [self.prefer] + [n for n in found if n != self.prefer]
            self._cands = found
        return self._cands

    def pick_model(self) -> str:
        now = time.time()
        if self.fast and not self.fixed and self.model and self._cool.get(self.model, 0) > now:
            self.model = ""
        if (self.fast and self.main and self.model != self.main and self.main not in self._bad
                and self._cool.get(self.main, 0) <= now):
            self.model = self.main      # model chính có lượt lại rồi: quay về dùng nó (dịch tốt hơn model tạm)
        if not self.model or self.model in self._bad:
            ok = [m for m in self.candidates() if m not in self._bad]
            ready = self._rotation([m for m in ok if self._cool.get(m, 0) <= now])
            self.model = (ready or ok or [""])[0]
        if not self.model:
            reasons = "\n".join(f"- {m}: {r}" for m, r in list(self._bad.items())[:6])
            raise TranslateError("Key này chưa dùng được model Gemini nào ở gói hiện tại.\n" + reasons)
        return self.model

    def _rotation(self, names: list[str]) -> list[str]:
        """Thứ tự dùng tạm: model chính, model đã chạy được, rồi bản Lite (nhẹ, nhiều lượt), cuối cùng mới tới model chưa thử."""
        if not self.main:
            return names
        return sorted(names, key=lambda n: 0 if n == self.main else 1 if n in self.used else 2 if "lite" in n else 3)

    def _body(self, src, target, source, domain, glossary, context) -> dict:
        cfg = {"temperature": 0.15, "maxOutputTokens": 32000}
        if self.use_thinking_cfg:
            m = re.search(r"gemini-(\d+)(?:\.(\d+))?", self.model or "")
            major = int(m.group(1)) if m else 3
            if major >= 3:
                cfg["thinkingConfig"] = {"thinkingLevel": "low"}
            elif (major, int(m.group(2) or 0) if m else 0) >= (2, 5):
                cfg["thinkingConfig"] = {"thinkingBudget": 0}
        if self.use_schema:
            cfg.update({"responseMimeType": "application/json",
                        "responseSchema": {"type": "ARRAY", "items": {"type": "STRING"}}})
        return {"systemInstruction": {"parts": [{"text": build_prompt(target, source, domain, glossary, context)}]},
                "contents": [{"role": "user", "parts": [{"text": json.dumps(src, ensure_ascii=False)}]}],
                "generationConfig": cfg}

    def translate_batch(self, src, target, source, progress=None, domain="general", glossary="", context="", **_):
        waits = 0
        for _attempt in range(40):
            self._check()
            model = self.pick_model()
            url = f"{self.base}/models/{urllib.parse.quote(model)}:generateContent"
            data = json.dumps(self._body(src, target, source, domain, glossary, context)).encode("utf-8")
            temp = bool(self.main) and model != self.main and model not in self.used   # model dùng tạm, chưa biết có chạy không
            try:
                raw = _http(url, data, {"Content-Type": "application/json", "x-goog-api-key": self.key},
                            timeout=40 if temp else self.timeout)
                j = json.loads(raw)
                cands = j.get("candidates") or []
                if not cands:
                    reason = (j.get("promptFeedback") or {}).get("blockReason", "không rõ")
                    raise TranslateError(f"Gemini từ chối đoạn này (lý do: {reason}).")
                text = "".join(p.get("text", "") for p in (cands[0].get("content") or {}).get("parts", []))
                if cands[0].get("finishReason") == "MAX_TOKENS" and len(src) > 1:
                    raise TooSlow("lô quá dài")      # trả lời bị cắt giữa chừng: chia nhỏ lô
                self.used.add(model)
                self.main = self.main or model
                return _parse_array(text, len(src))
            except urllib.error.HTTPError as e:
                msg = _http_error_text(e)
                low = msg.lower()
                if e.code in (400, 401, 403) and ("api key" in low or "api_key" in low):
                    raise TranslateError("Google báo API key không hợp lệ. Hãy sao chép lại đúng cả chuỗi key.\n" + msg)
                if e.code == 400 and self.use_thinking_cfg and "thinking" in low:
                    self.use_thinking_cfg = False   # model này không nhận tuỳ chọn "nghĩ ít": gọi lại không kèm
                    continue
                if e.code == 400 and self.use_schema and ("schema" in low or "mime" in low or "json mode" in low):
                    self.use_schema = False      # model này không nhận kiểu trả về JSON: gọi lại kiểu thường
                    continue
                no_access = e.code in (403, 404) or (e.code == 429 and ("limit: 0" in low or "free_tier" in low
                                                                         and "limit: 0" in low))
                if no_access and not self.fixed:
                    self._bad[model] = f"lỗi {e.code}: {msg[:140]}"   # key không có quyền/hết suất với model này: thử model kế
                    self.model = ""
                    continue
                if e.code == 429 or e.code >= 500:   # hết lượt trong phút này hoặc máy chủ bận
                    if self.quick and not self.fixed and len(self._bad) < 3:
                        self._bad[model] = f"lỗi {e.code}: đang quá tải hoặc hết lượt ({msg[:100]})"
                        self.model = ""      # lúc kiểm tra key: model này đang bận thì thử ngay model kế tiếp
                        continue
                    if self.quick:
                        raise TranslateError(f"Model {model} đang báo quá tải hoặc hết lượt gọi (lỗi {e.code}). "
                                             f"Key vẫn có thể đúng; thử lại sau một phút.\n{msg}")
                    daily = e.code == 429 and ("perday" in low.replace(" ", "").replace("_", "") or "per day" in low)
                    wait = 20 * (waits + 1)
                    m = re.search(r"retry in ([\d.]+)s", msg)
                    if m:
                        wait = min(90, float(m.group(1)) + 2)
                    if daily and not self.fixed:
                        self._bad[model] = "đã hết lượt gọi miễn phí của hôm nay"
                        self.model = ""
                        continue                 # hết suất trong ngày của model này: chờ cũng vô ích, đổi model
                    if daily:
                        raise TranslateError(f"Model {model} đã hết lượt gọi miễn phí của hôm nay. Thử lại vào ngày mai, "
                                             "để trống ô Model cho app tự chọn model khác, hoặc dùng gói trả phí.\n" + msg)
                    if self.fast and not self.fixed:
                        self._cool[model] = time.time() + wait
                        others = self._rotation([x for x in self.candidates() if x not in self._bad and x != model
                                                 and self._cool.get(x, 0) <= time.time()])
                        if others:               # model này hết lượt trong phút: dùng tạm model khác thay vì ngồi chờ
                            self.model = ""
                            if progress:
                                progress(-1, -1, f"{model} hết lượt trong phút này, chuyển tạm sang {others[0]}…")
                            continue
                        wait = max(1.0, min(self._cool.values()) - time.time())
                    waits += 1
                    if waits > 8:
                        raise TranslateError("Gemini báo đã hết lượt gọi của gói miễn phí hoặc máy chủ đang bận. "
                                             "Hãy thử lại sau ít phút.\n" + msg)
                    self._sleep(wait, (lambda s: progress(-1, -1, f"Hết lượt gọi miễn phí trong phút này, tự dịch tiếp "
                                                                    f"sau {s} giây…")) if progress else None)
                    continue
                if e.code == 404:
                    raise TranslateError(f"Không có model “{model}”. Hãy để trống ô Model để app tự chọn.\n{msg}")
                raise TranslateError(f"Gemini báo lỗi {e.code} với model {model}: {msg}")
            except urllib.error.URLError as e:
                if is_timeout(e) and temp:
                    self._bad[model] = "không trả lời sau 40 giây"   # model dùng tạm bị treo: bỏ hẳn, không thử lại
                    self.model = ""
                    continue
                if is_timeout(e) and not self.quick and len(src) > 12:
                    raise TooSlow(f"model {model} không kịp trả lời lô {len(src)} đoạn")
                if is_timeout(e):
                    self.slow += 1
                    if not self.quick and self.slow <= 1:
                        if progress:
                            progress(-1, -1, f"Model {model} trả lời chậm, đang thử lại…")
                        continue
                    if not self.fixed and len(self._bad) < 3:
                        self._bad[model] = f"không trả lời sau {self.timeout:g} giây"
                        self.model, self.slow = "", 0      # model này quá chậm: chuyển sang model kế (thường nhẹ hơn)
                        continue
                    raise TranslateError(f"Model {model} không trả lời sau {self.timeout:g} giây. Kết nối tới Google "
                                         "thì được nhưng máy chủ phản hồi quá chậm; thử lại sau ít phút.")
                raise TranslateError("Không kết nối được tới máy chủ Gemini của Google. Kiểm tra mạng, tường lửa hoặc "
                                     f"proxy của công ty.\nChi tiết: {e.reason}")
        raise TranslateError("Gemini không phản hồi.")


class OpenAICompatEngine(Engine):
    """Mọi dịch vụ theo chuẩn OpenAI: OpenAI, OpenRouter, Groq, hoặc AI chạy ngay trên máy (Ollama, LM Studio)."""
    name = "AI chuẩn OpenAI"

    def __init__(self, base_url: str, api_key: str, model: str):
        super().__init__()
        self.base = (base_url.strip() or "https://api.openai.com/v1").rstrip("/")
        self.key = api_key.strip()
        self.model = model.strip()
        if not self.model:
            raise TranslateError("Chưa nhập tên model.")

    def translate_batch(self, src, target, source, progress=None, domain="general", glossary="", context="", **_):
        sysmsg = build_prompt(target, source, domain, glossary, context) + \
            '\nReturn a JSON object of the form {"t": ["...", "..."]}.'
        body = {"model": self.model, "temperature": 0.15,
                "messages": [{"role": "system", "content": sysmsg},
                             {"role": "user", "content": json.dumps(src, ensure_ascii=False)}],
                "response_format": {"type": "json_object"}}
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = "Bearer " + self.key
        for attempt in range(5):
            self._check()
            try:
                raw = _http(self.base + "/chat/completions", json.dumps(body).encode("utf-8"), headers, timeout=300)
                j = json.loads(raw)
                return _parse_array(j["choices"][0]["message"]["content"], len(src))
            except urllib.error.HTTPError as e:
                msg = _http_error_text(e)
                if (e.code == 429 or e.code >= 500) and attempt < 4:
                    self._sleep(15 * (attempt + 1), (lambda s: progress(-1, -1, f"Máy chủ đang bận, chờ {s} giây…"))
                                if progress else None)
                    continue
                if e.code == 400 and "response_format" in msg and "response_format" in body:
                    body.pop("response_format")
                    continue
                raise TranslateError(f"Dịch vụ AI báo lỗi {e.code}: {msg}")
            except urllib.error.URLError as e:
                raise TranslateError(f"Không kết nối được tới {self.base}.\n{e.reason}")
            except (KeyError, IndexError):
                raise TranslateError("Dịch vụ AI trả về dữ liệu không đúng định dạng.")
        raise TranslateError("Dịch vụ AI không phản hồi.")


class GoogleFreeEngine(Engine):
    """Google Translate miễn phí, không cần key (cổng không chính thức, có thể bị giới hạn bất chợt)."""
    name = "Google Translate (miễn phí)"
    url = "https://translate.googleapis.com/translate_a/single"
    batch_items, batch_chars = 60, 3200

    def _one(self, text: str, target: str, source: str) -> str:
        q = urllib.parse.urlencode({"client": "gtx", "sl": source or "auto", "tl": target, "dt": "t", "q": text})
        for attempt in range(4):
            self._check()
            try:
                raw = _http(self.url, q.encode("utf-8"),
                            {"Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
                             "User-Agent": "Mozilla/5.0"}, timeout=60)
                j = json.loads(raw)
                return "".join(seg[0] for seg in (j[0] or []) if seg and seg[0])
            except urllib.error.HTTPError as e:
                if e.code in (429, 503) and attempt < 3:
                    self._sleep(8 * (attempt + 1))
                    continue
                raise TranslateError(f"Google Translate báo lỗi {e.code}. Có thể đang bị giới hạn lượt, thử lại sau "
                                     "hoặc chuyển sang Gemini.")
            except urllib.error.URLError as e:
                raise TranslateError(f"Không kết nối được tới Google Translate. Kiểm tra mạng.\n{e.reason}")
            except Exception:
                raise TranslateError("Google Translate trả về dữ liệu không đọc được.")
        raise TranslateError("Google Translate không phản hồi.")

    def translate_batch(self, src, target, source, progress=None, **_):
        code = lang_name(target)[0]
        scode = lang_name(source)[0] if source else ""
        joined = "\n".join(s.replace("\n", " ") for s in src)
        parts = [p.strip() for p in self._one(joined, code, scode).split("\n")]
        if len(parts) == len(src):
            return parts
        return [self._one(s, code, scode) for s in src]   # Google gộp/tách dòng: dịch lại từng câu


SERVERS = [  # máy chủ theo chuẩn OpenAI hay dùng: (tên, địa chỉ, cần key, trang lấy key)
    ("OpenAI", "https://api.openai.com/v1", True, "https://platform.openai.com/api-keys"),
    ("OpenRouter (nhiều hãng, có model miễn phí)", "https://openrouter.ai/api/v1", True, "https://openrouter.ai/keys"),
    ("Groq (nhanh, có gói miễn phí)", "https://api.groq.com/openai/v1", True, "https://console.groq.com/keys"),
    ("Ollama trên máy này (không cần key)", "http://localhost:11434/v1", False, "https://ollama.com/download"),
    ("LM Studio trên máy này (không cần key)", "http://localhost:1234/v1", False, "https://lmstudio.ai"),
]


def env_keys() -> dict:
    """API key đã khai báo sẵn trong biến môi trường của máy này (nếu có)."""
    e = os.environ
    return {"gemini": e.get("GEMINI_API_KEY") or e.get("GOOGLE_API_KEY") or "",
            "openai": e.get("OPENAI_API_KEY") or e.get("OPENROUTER_API_KEY") or e.get("GROQ_API_KEY") or ""}


def list_models(base_url: str, api_key: str = "", timeout: float = 10) -> list[str]:
    """Hỏi máy chủ chuẩn OpenAI xem có những model nào."""
    headers = {"Authorization": "Bearer " + api_key.strip()} if api_key.strip() else {}
    try:
        raw = _http(base_url.rstrip("/") + "/models", headers=headers, timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise TranslateError("Máy chủ từ chối: API key thiếu hoặc không đúng.")
        raise TranslateError(f"Máy chủ báo lỗi {e.code}: {_http_error_text(e)}")
    except Exception as e:
        raise TranslateError(f"Không kết nối được tới {base_url}.\n{getattr(e, 'reason', e)}")
    try:
        j = json.loads(raw)
        items = j.get("data") if isinstance(j, dict) else j
        names = sorted({m["id"] for m in items if isinstance(m, dict) and m.get("id")})
    except Exception:
        raise TranslateError("Máy chủ trả về danh sách model không đọc được.")
    skip = ("embed", "whisper", "tts", "dall", "image", "audio", "moderation", "rerank", "realtime", "transcribe")
    return [n for n in names if not any(k in n.lower() for k in skip)]


def detect_local() -> list[tuple[str, str, list[str]]]:
    """Dò AI đang chạy ngay trên máy (Ollama, LM Studio). Trả về [(tên, địa chỉ, [model...])]."""
    found = []
    for name, base, need_key, _url in SERVERS:
        if need_key:
            continue
        try:
            models = list_models(base, "", timeout=0.6)
        except Exception:
            continue
        found.append((name, base, models))
    return found


CHECK_TIMEOUT = 45      # giây chờ mỗi model khi dịch thử
LIST_TIMEOUT = 20


def check_gemini(api_key: str, cancel_holder: list | None = None, model: str = "", status=None,
                 prefer: str = "") -> dict:
    """Kiểm tra key Gemini theo hai bước và nói rõ vướng ở bước nào.
    Trả về {"ok": bool, "key_ok": bool, "model": str, "lines": [các dòng giải thích]}."""
    res = {"ok": False, "key_ok": False, "model": "", "lines": []}
    px = system_proxy()

    def say(t):
        if status:
            status(t)
    # --- bước 1: tới được Google và key hợp lệ không
    say("Bước 1/2: kết nối tới Google và kiểm tra key…")
    eng = GeminiEngine(api_key, model, quick=True)
    if cancel_holder is not None:
        cancel_holder.append(eng)
    t0 = time.time()
    probe = GeminiEngine(api_key, "", quick=True, prefer=prefer)   # model lần trước chạy được thì thử trước
    try:
        cands = probe.candidates()
    except TranslateError as e:
        res["lines"].append("Bước 1 (kết nối và kiểm tra key) không qua: " + str(e))
        if px:
            res["lines"].append(f"Máy này đang đặt proxy hệ thống: {px}. App đã thử cả qua proxy lẫn đi thẳng.")
        return res
    if probe.listed < 0:
        res["lines"].append("Bước 1: không lấy được danh sách model từ Google, app dùng danh sách dự phòng.")
    else:
        res["key_ok"] = True
        res["lines"].append(f"Bước 1: kết nối được Google và key hợp lệ ({probe.listed} model, {time.time() - t0:.1f} giây"
                            + (", đi thẳng không qua proxy" if _net["direct"] else "") + ").")
    # --- bước 2: dịch thử một câu, lần lượt với tối đa 3 model
    tried = [model] if model else cands[:3]
    for m in tried:
        if eng.cancel:
            raise Cancelled()
        say(f"Bước 2/2: dịch thử một câu bằng model {m}…")
        one = GeminiEngine(api_key, m, quick=True)
        one.timeout = CHECK_TIMEOUT
        one.cancel = eng.cancel
        if cancel_holder is not None:
            cancel_holder.append(one)
        t1 = time.time()
        try:
            out = one.translate_batch(["Xin chào"], "en", "")
            res.update(ok=True, model=m)
            res["lines"].append(f"Bước 2: model {m} dịch thử được ({time.time() - t1:.1f} giây): “{out[0] if out else ''}”.")
            return res
        except TranslateError as e:
            res["lines"].append(f"Bước 2: model {m} chưa được: " + str(e).replace("\n", " ")[:260])
    return res


def make_engine(kind: str, cfg: dict) -> Engine:
    if kind == "gemini":
        return GeminiEngine(cfg.get("gemini_key", ""), cfg.get("gemini_model", ""),
                            prefer=cfg.get("gemini_prefer", ""), fast=bool(cfg.get("gemini_fast", False)))
    if kind == "openai":
        return OpenAICompatEngine(cfg.get("openai_base", ""), cfg.get("openai_key", ""), cfg.get("openai_model", ""))
    return GoogleFreeEngine()


# =============================================================== quy trình
def collect(doc, pages: list[int], with_toc: bool = True, image_reader=None, progress=None, store=None) -> dict:
    """Bước 1: gom mọi đoạn chữ cần dịch. image_reader: hàm OCR để đọc cả chữ nằm trong hình ảnh (None = bỏ qua)."""
    job = {"pages": [], "texts": [], "skipped_rot": 0, "no_text": [], "toc": None, "context": "", "img_units": 0,
           "img_seen": 0, "img_lines": 0}
    ctx = []
    seen = read_images(doc, pages, image_reader, store, progress) if image_reader is not None else {}
    job["img_seen"] = len(seen)
    job["img_lines"] = sum(len(v) for v in seen.values())
    for n, i in enumerate(pages):
        try:
            units, sk = page_units(doc[i])
        except Exception:
            units, sk = [], 0
        if image_reader is not None:
            extra = image_units(doc[i], lambda pix, key: seen.get(key, []))
            job["img_units"] += len(extra)
            units += extra
        job["skipped_rot"] += sk
        if not units:
            try:      # trang không có chữ nhìn thấy nào (ảnh / bản scan, kể cả bản scan đã OCR chỉ có lớp chữ ẩn)
                vis = any(sp["text"].strip() and sp.get("alpha", 255) != 0 for b in tools.text_dict(doc[i]).get("blocks", [])
                          for ln in b.get("lines", []) for sp in ln["spans"])
                if not vis:
                    job["no_text"].append(i)
            except Exception:
                pass
        start = len(job["texts"])
        job["texts"] += [u["text"] for u in units]
        job["pages"].append((i, units, start))
        if sum(map(len, ctx)) < 1500:
            ctx += [u.get("plain") or u["text"] for u in units[:12]]
    if with_toc:
        try:
            toc = doc.get_toc(simple=False)
        except Exception:
            toc = []
        if toc:
            job["toc"] = (toc, len(job["texts"]))
            job["texts"] += [t[1] for t in toc]
    job["context"] = " | ".join(ctx)[:1500]
    return job


def apply(doc, job: dict, translations: list[str], progress=None) -> dict:
    """Bước 3: ghép bản dịch vào bản sao của tài liệu. Trả về thống kê."""
    done = total = 0
    for k, (i, units, start) in enumerate(job["pages"]):
        total += len(units)
        if units:
            try:
                done += apply_page(doc[i], units, translations[start:start + len(units)])
            except Exception:
                pass
        if progress:
            progress(k + 1, len(job["pages"]))
    if job.get("toc"):
        toc, start = job["toc"]
        new = []
        for k, (lvl, _title, page, dest) in enumerate(toc):
            d = {a: b for a, b in (dest or {}).items() if a != "xref"}
            new.append([lvl, translations[start + k].strip() or toc[k][1], page, d])
        try:
            doc.set_toc(new)
        except Exception:
            pass
    tools.finalize_fonts(doc)
    return {"units": total, "replaced": done, "no_text": job["no_text"], "skipped_rot": job["skipped_rot"]}
