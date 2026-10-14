"""So sánh nội dung chữ của hai tài liệu PDF và tìm vị trí các chỗ khác nhau (để tô sáng khi so sánh song song).

Phần này chỉ làm việc với dữ liệu thường (chuỗi, bộ số) nên chạy được ở luồng phụ, không đụng tới PyMuPDF."""
from __future__ import annotations

import unicodedata
from difflib import SequenceMatcher


def page_words(page) -> list[tuple[str, tuple]]:
    """Các từ của một trang theo thứ tự đọc: [(từ, (x0, y0, x1, y1)), ...] (toạ độ trang chưa xoay)."""
    # xếp theo vị trí trên trang (trên xuống, trái sang phải) chứ không theo thứ tự ghi trong file: chữ vừa sửa thường
    # được ghi ở cuối nội dung trang, xếp theo vị trí thì nó mới nằm đúng chỗ cũ khi đem so
    from .tools import page_words as _pw
    ws = _pw(page, sort=True)
    return [(unicodedata.normalize("NFC", w[4]), (w[0], w[1], w[2], w[3])) for w in ws if w[4].strip()]


def _merge(items: list[tuple[int, tuple]]) -> list[tuple[int, tuple]]:
    """Gộp các từ liền nhau trên cùng một dòng thành một dải, cho vùng tô liền mạch."""
    out: list[list] = []
    for pg, r in items:
        if out:
            lp, lr = out[-1]
            h = min(lr[3] - lr[1], r[3] - r[1])
            overlap = min(lr[3], r[3]) - max(lr[1], r[1])
            if lp == pg and h > 0 and overlap > 0.5 * h and -0.5 * h <= r[0] - lr[2] <= 1.5 * h:
                out[-1][1] = (min(lr[0], r[0]), min(lr[1], r[1]), max(lr[2], r[2]), max(lr[3], r[3]))
                continue
        out.append([pg, r])
    return [(pg, r) for pg, r in out]


def compare(a: list[list], b: list[list]) -> list[dict]:
    """a, b: danh sách trang, mỗi trang là danh sách page_words. Trả về các chỗ khác nhau theo thứ tự tài liệu:
    [{"a": [(trang, khung)], "b": [...], "a_pages": [trang chỉ có ở a], "b_pages": [...]}, ...]."""
    ha = [hash(tuple(t for t, _r in p)) for p in a]
    hb = [hash(tuple(t for t, _r in p)) for p in b]
    hunks: list[dict] = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, ha, hb, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        wa = [(i, t, r) for i in range(i1, i2) for t, r in a[i]]
        wb = [(j, t, r) for j in range(j1, j2) for t, r in b[j]]
        if tag in ("delete", "insert") or not wa or not wb:
            # cả trang chỉ có ở một bên (trang thêm / bớt, hoặc trang không có chữ nào để dò)
            hunks.append({"a": _merge([(i, r) for i, _t, r in wa]), "b": _merge([(j, r) for j, _t, r in wb]),
                          "a_pages": list(range(i1, i2)) if not wb else [], "b_pages": list(range(j1, j2)) if not wa else []})
            continue
        ta, tb = [t for _i, t, _r in wa], [t for _j, t, _r in wb]
        sm = SequenceMatcher(None, ta, tb, autojunk=len(ta) + len(tb) > 40000)
        for tag2, x1, x2, y1, y2 in sm.get_opcodes():
            if tag2 == "equal":
                continue
            hunks.append({"a": _merge([(i, r) for i, _t, r in wa[x1:x2]]), "b": _merge([(j, r) for j, _t, r in wb[y1:y2]]),
                          "a_pages": [], "b_pages": [],
                          # chỗ chỉ có ở một bên: nhớ vị trí tương ứng bên kia để còn cuộn tới
                          "a_at": (wa[min(x1, len(wa) - 1)][0], wa[min(x1, len(wa) - 1)][2]),
                          "b_at": (wb[min(y1, len(wb) - 1)][0], wb[min(y1, len(wb) - 1)][2])})
    return hunks
