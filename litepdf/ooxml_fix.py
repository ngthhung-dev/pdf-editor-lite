"""Chuẩn hoá file .docx / .xlsx sau khi xuất để đúng lược đồ Office Open XML.

Thư viện pdf2docx và openpyxl đôi khi ghi thẻ sai thứ tự hoặc giá trị không hợp lệ
(w:w số lẻ, màu có dấu #...). Word/Excel bản mới thường bỏ qua, nhưng bản cũ,
WPS, Google Docs hay công cụ kiểm định có thể báo lỗi. Ở đây sắp lại cho đúng chuẩn.
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import zipfile

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
X = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

_ORDER_W = {
    "pPr": "pStyle keepNext keepLines pageBreakBefore framePr widowControl numPr suppressLineNumbers pBdr shd tabs "
           "suppressAutoHyphens kinsoku wordWrap overflowPunct topLinePunct autoSpaceDE autoSpaceDN bidi adjustRightInd "
           "snapToGrid spacing ind contextualSpacing mirrorIndents suppressOverlap jc textDirection textAlignment "
           "textboxTightWrap outlineLvl divId cnfStyle rPr sectPr pPrChange",
    "rPr": "rStyle rFonts b bCs i iCs caps smallCaps strike dstrike outline shadow emboss imprint noProof snapToGrid "
           "vanish webHidden color spacing w kern position sz szCs highlight u effect bdr shd fitText vertAlign rtl cs "
           "em lang eastAsianLayout specVanish oMath",
    "tcPr": "cnfStyle tcW gridSpan hMerge vMerge tcBorders shd noWrap tcMar textDirection tcFitText vAlign hideMark",
    "tcBorders": "top left start bottom right end insideH insideV tl2br tr2bl",
    "tblBorders": "top left start bottom right end insideH insideV",
    "tblPr": "tblStyle tblpPr tblOverlap bidiVisual tblStyleRowBandSize tblStyleColBandSize tblW jc tblCellSpacing "
             "tblInd tblBorders shd tblLayout tblCellMar tblLook",
    "sectPr": "headerReference footerReference footnotePr endnotePr type pgSz pgMar paperSrc pgBorders lnNumType "
              "pgNumType cols formProt vAlign noEndnote titlePg textDirection bidi rtlGutter docGrid printerSettings",
}
_ORDER_X = {
    "font": "b i strike condense extend outline shadow u vertAlign sz color name family charset scheme",
}
_INT_ATTR = {"w", "sz", "szCs", "kern", "position"}
_REPEAT = {"headerReference", "footerReference"}
_FLOAT = re.compile(r"^-?\d+\.\d*$")
_HEX = re.compile(r"^[0-9A-Fa-f]{6}$")


def _sort(el, ns, order):
    rank = {n: i for i, n in enumerate(order.split())}
    kids = list(el)
    if len(kids) < 2:
        return
    def key(c):
        if not isinstance(c.tag, str):
            return len(rank) + 1
        q = etree.QName(c)
        return rank.get(q.localname, len(rank)) if q.namespace == ns else len(rank)
    srt, seen = [], set()
    for c in sorted(kids, key=key):  # sorted ổn định: giữ thứ tự gốc khi cùng hạng
        q = etree.QName(c).localname if isinstance(c.tag, str) else None
        if q in rank and q not in _REPEAT:
            if q in seen:            # thẻ chỉ được có một lần mà bị lặp: bỏ bản sau
                continue
            seen.add(q)
        srt.append(c)
    if srt != kids:
        for c in kids:
            el.remove(c)
        el.extend(srt)


def _fix_word(root):
    val = f"{{{W}}}val"
    for name, order in _ORDER_W.items():
        for el in root.iter(f"{{{W}}}{name}"):
            _sort(el, W, order)
    for el in root.iter():
        if not isinstance(el.tag, str) or not el.tag.startswith(f"{{{W}}}"):
            continue
        ln = etree.QName(el).localname
        attrs = [f"{{{W}}}color", f"{{{W}}}fill"] + ([val] if ln == "color" else [])
        for a in attrs:
            v = el.get(a)
            if v is None:
                continue
            v = v.lstrip("#")
            el.set(a, v if (v == "auto" or _HEX.match(v)) else "auto")
        for a, v in list(el.attrib.items()):  # số đo trong Word luôn là số nguyên (twip, 1/8 pt…)
            if a.startswith(f"{{{W}}}") and _FLOAT.match(v):
                el.set(a, str(round(float(v))))
        v = el.get(val)
        if ln in _INT_ATTR and v is not None and not v.lstrip("-").isdigit():
            try:
                n = round(float(v))
                if ln == "w":
                    n = min(600, max(1, n))
                el.set(val, str(n))
            except ValueError:
                del el.attrib[val]


    for el in root.iter(f"{{{W}}}shd"):
        if el.get(val) is None:
            el.set(val, "clear")
    for el in root.iter(f"{{{W}}}pgSz"):       # Word không mở được trang lớn hơn 22 inch
        for a in ("w", "h"):
            k = f"{{{W}}}{a}"
            if el.get(k, "0").isdigit() and int(el.get(k)) > 31680:
                el.set(k, "31680")


def _fix_xlsx(root):
    for name, order in _ORDER_X.items():
        for el in root.iter(f"{{{X}}}{name}"):
            _sort(el, X, order)


def fix(path: str) -> None:
    """Sửa tại chỗ. Lỗi gì thì giữ nguyên file gốc (không làm hỏng kết quả)."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        targets = re.compile(r"^word/(document|header\d*|footer\d*|footnotes|endnotes|styles)\.xml$")
        fn = _fix_word
    elif ext == ".xlsx":
        targets = re.compile(r"^xl/styles\.xml$")
        fn = _fix_xlsx
    else:
        return
    fd, tmp = tempfile.mkstemp(suffix=ext, dir=os.path.dirname(os.path.abspath(path)))
    os.close(fd)
    try:
        with zipfile.ZipFile(path) as zi, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zo:
            names = zi.namelist()
            # [Content_Types].xml phải đứng đầu gói
            names.sort(key=lambda n: n != "[Content_Types].xml")
            for n in names:
                data = zi.read(n)
                if targets.match(n):
                    root = etree.fromstring(data)
                    fn(root)
                    data = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
                zo.writestr(n, data)
        shutil.move(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
