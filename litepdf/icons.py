"""Biểu tượng vẽ bằng nét (không cần file ảnh) cho thanh công cụ và menu."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap, QPolygonF


def _poly(p, pts, closed=False):
    q = QPolygonF([QPointF(x, y) for x, y in pts])
    (p.drawPolygon if closed else p.drawPolyline)(q)


def _path(p, d):
    path = QPainterPath()
    for cmd in d:
        if cmd[0] == "M":
            path.moveTo(cmd[1], cmd[2])
        elif cmd[0] == "L":
            path.lineTo(cmd[1], cmd[2])
        else:
            path.cubicTo(*cmd[1:])
    p.drawPath(path)


def _letter_a(p):
    _poly(p, [(7, 16), (12, 4), (17, 16)])
    p.drawLine(QPointF(9, 12), QPointF(15, 12))


def _bar(p, color, y=20, w=3.2):
    pen = p.pen()
    p.setPen(QPen(QColor(color), w, Qt.SolidLine, Qt.FlatCap))
    p.drawLine(QPointF(4, y), QPointF(20, y))
    p.setPen(pen)


def _mag(p):
    p.drawEllipse(QPointF(10, 10), 6, 6)
    p.drawLine(QPointF(14.5, 14.5), QPointF(21, 21))


ICONS = {
    "open": lambda p: _poly(p, [(3, 6), (9, 6), (11, 8.5), (21, 8.5), (21, 19), (3, 19)], True),
    "save": lambda p: (p.drawRoundedRect(QRectF(4, 4, 16, 16), 1.5, 1.5), p.drawRect(QRectF(8, 4, 7, 5)),
                       p.drawRect(QRectF(7, 13, 10, 7))),
    "print": lambda p: (p.drawRect(QRectF(7, 3, 10, 5)), p.drawRoundedRect(QRectF(3, 8, 18, 9), 1.5, 1.5),
                        p.drawRect(QRectF(7, 14, 10, 7))),
    "undo": lambda p: (_path(p, [("M", 5, 9), ("L", 14, 9), ("C", 21, 9, 21, 19, 14, 19), ("L", 9, 19)]),
                       _poly(p, [(9, 5), (5, 9), (9, 13)])),
    "redo": lambda p: (_path(p, [("M", 19, 9), ("L", 10, 9), ("C", 3, 9, 3, 19, 10, 19), ("L", 15, 19)]),
                       _poly(p, [(15, 5), (19, 9), (15, 13)])),
    "zoomin": lambda p: (_mag(p), p.drawLine(QPointF(7, 10), QPointF(13, 10)), p.drawLine(QPointF(10, 7), QPointF(10, 13))),
    "zoomout": lambda p: (_mag(p), p.drawLine(QPointF(7, 10), QPointF(13, 10))),
    "fitw": lambda p: (p.drawRect(QRectF(6, 3, 12, 18)), p.drawLine(QPointF(8.5, 12), QPointF(15.5, 12)),
                       _poly(p, [(10.5, 10), (8.5, 12), (10.5, 14)]), _poly(p, [(13.5, 10), (15.5, 12), (13.5, 14)])),
    "fitp": lambda p: (p.drawRect(QRectF(6, 3, 12, 18)), p.drawLine(QPointF(12, 6.5), QPointF(12, 17.5)),
                       _poly(p, [(10, 8.5), (12, 6.5), (14, 8.5)]), _poly(p, [(10, 15.5), (12, 17.5), (14, 15.5)])),
    "hand": lambda p: _poly(p, [(6, 3), (6, 19), (10, 15.5), (13, 21), (15.5, 20), (12.5, 14.5), (18, 14.5)], True),
    "select": lambda p: (p.drawLine(QPointF(9, 4), QPointF(15, 4)), p.drawLine(QPointF(12, 4), QPointF(12, 20)),
                         p.drawLine(QPointF(9, 20), QPointF(15, 20))),
    "highlight": lambda p: (_bar(p, "#ffd400", 12, 13), _letter_a(p)),
    "underline": lambda p: (_letter_a(p), _bar(p, "#e02020", 20, 2)),
    "strike": lambda p: (_letter_a(p), _bar(p, "#e02020", 9, 2)),
    "note": lambda p: (p.drawRoundedRect(QRectF(3, 4, 18, 12), 2, 2), _poly(p, [(7, 16), (7, 21), (12, 16)])),
    "text": lambda p: (p.drawLine(QPointF(5, 5), QPointF(19, 5)), p.drawLine(QPointF(12, 5), QPointF(12, 20))),
    "edittext": lambda p: (p.drawLine(QPointF(3, 5), QPointF(13, 5)), p.drawLine(QPointF(8, 5), QPointF(8, 17)),
                           _poly(p, [(12, 21), (13, 17), (19, 11), (22, 14), (16, 20)], True)),
    "rect": lambda p: p.drawRect(QRectF(4, 6, 16, 12)),
    "ellipse": lambda p: p.drawEllipse(QRectF(4, 6, 16, 12)),
    "line": lambda p: p.drawLine(QPointF(4, 20), QPointF(20, 4)),
    "arrow": lambda p: (p.drawLine(QPointF(4, 20), QPointF(20, 4)), _poly(p, [(13, 4), (20, 4), (20, 11)])),
    "ink": lambda p: _path(p, [("M", 3, 16), ("C", 7, 2, 10, 24, 13, 12), ("C", 15, 5, 19, 6, 21, 14)]),
    "image": lambda p: (p.drawRect(QRectF(3, 5, 18, 14)), _poly(p, [(3, 17), (9, 11), (13, 15), (16, 12), (21, 17)]),
                        p.drawEllipse(QPointF(16, 9), 1.2, 1.2)),
    "erase": lambda p: (_poly(p, [(10, 5), (20, 5), (14, 16), (4, 16)], True), p.drawLine(QPointF(3, 20), QPointF(21, 20))),
    "handsign": lambda p: (_path(p, [("M", 3, 16), ("C", 6, 4, 8, 20, 11, 13), ("C", 13, 9, 15, 18, 20, 12)]),
                           p.drawLine(QPointF(3, 20.5), QPointF(21, 20.5))),
    "sign": lambda p: (_poly(p, [(12, 3), (20, 6), (20, 13), (12, 21), (4, 13), (4, 6)], True),
                       _path(p, [("M", 7, 13), ("C", 9, 8, 10, 17, 12, 12), ("C", 13, 10, 15, 15, 17, 11)])),
    "verify": lambda p: (_poly(p, [(12, 3), (20, 6), (20, 13), (12, 21), (4, 13), (4, 6)], True),
                         _poly(p, [(8, 12), (11, 15), (16, 9)])),
    "rotl": lambda p: (p.drawArc(QRectF(5, 6, 14, 14), 90 * 16, -270 * 16), _poly(p, [(12, 2.5), (8.5, 6), (12, 9.5)])),
    "rotr": lambda p: (p.drawArc(QRectF(5, 6, 14, 14), 90 * 16, 270 * 16), _poly(p, [(12, 2.5), (15.5, 6), (12, 9.5)])),
    "delete": lambda p: (p.drawLine(QPointF(4, 7), QPointF(20, 7)), _poly(p, [(7, 7), (8, 21), (16, 21), (17, 7)]),
                         p.drawLine(QPointF(10, 4), QPointF(14, 4))),
    "merge": lambda p: (p.drawRect(QRectF(3, 3, 7, 8)), p.drawRect(QRectF(3, 13, 7, 8)), p.drawRect(QRectF(15, 7, 6, 10)),
                        _poly(p, [(10, 7), (12.5, 7), (12.5, 17), (10, 17)]), p.drawLine(QPointF(12.5, 12), QPointF(15, 12))),
    "split": lambda p: (p.drawRect(QRectF(3, 7, 6, 10)), p.drawRect(QRectF(14, 3, 7, 8)), p.drawRect(QRectF(14, 13, 7, 8)),
                        _poly(p, [(14, 7), (11.5, 7), (11.5, 17), (14, 17)]), p.drawLine(QPointF(9, 12), QPointF(11.5, 12))),
    "compare": lambda p: (p.drawRect(QRectF(3, 4, 8, 16)), p.drawRect(QRectF(13, 4, 8, 16)),
                          p.drawLine(QPointF(5, 9), QPointF(9, 9)), p.drawLine(QPointF(15, 9), QPointF(19, 9)),
                          p.drawLine(QPointF(5, 13), QPointF(9, 13)), p.drawLine(QPointF(15, 13), QPointF(19, 13))),
    "diff": lambda p: (p.drawRect(QRectF(3, 4, 8, 16)), p.drawRect(QRectF(13, 4, 8, 16)),
                       p.fillRect(QRectF(4.6, 8, 4.8, 2.6), QColor("#ea4335")), p.fillRect(QRectF(14.6, 13, 4.8, 2.6), QColor("#1ea046"))),
    "diffnext": lambda p: (p.fillRect(QRectF(4, 5, 16, 3), QColor("#ea4335")), _poly(p, [(7, 13), (12, 19), (17, 13)]),
                           p.drawLine(QPointF(12, 10), QPointF(12, 19))),
    "diffprev": lambda p: (p.fillRect(QRectF(4, 16, 16, 3), QColor("#ea4335")), _poly(p, [(7, 11), (12, 5), (17, 11)]),
                           p.drawLine(QPointF(12, 14), QPointF(12, 5))),
    "syncscroll": lambda p: (p.drawLine(QPointF(8, 4), QPointF(8, 20)), p.drawLine(QPointF(16, 4), QPointF(16, 20)),
                             p.drawLine(QPointF(5, 7), QPointF(8, 4)), p.drawLine(QPointF(11, 7), QPointF(8, 4)),
                             p.drawLine(QPointF(13, 17), QPointF(16, 20)), p.drawLine(QPointF(19, 17), QPointF(16, 20))),
    "sidebar": lambda p: (p.drawRoundedRect(QRectF(3, 4, 18, 16), 1.5, 1.5), p.drawLine(QPointF(9, 4), QPointF(9, 20))),
    "lock": lambda p: (p.drawRoundedRect(QRectF(5, 11, 14, 10), 1.5, 1.5), p.drawArc(QRectF(8, 4, 8, 12), 0, 180 * 16)),
    "convert": lambda p: (p.drawLine(QPointF(4, 9), QPointF(19, 9)), _poly(p, [(16, 6), (19, 9), (16, 12)]),
                          p.drawLine(QPointF(20, 16), QPointF(5, 16)), _poly(p, [(8, 13), (5, 16), (8, 19)])),
}
_ACCENT = {"sign": "#188038", "verify": "#188038", "erase": "#d93025", "delete": "#d93025", "edittext": "#1a73e8"}
_icon_cache: dict[str, QIcon] = {}


def icon(name: str) -> QIcon:
    if name not in _icon_cache:
        pm = QPixmap(72, 72)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.scale(3, 3)
        p.setPen(QPen(QColor(_ACCENT.get(name, "#3c4654")), 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        ICONS[name](p)
        p.end()
        ic = QIcon(pm)
        faded = QPixmap(pm.size())   # bản mờ dùng khi mục không khả dụng
        faded.fill(Qt.transparent)
        fp = QPainter(faded)
        fp.setOpacity(0.28)
        fp.drawPixmap(0, 0, _gray(pm))
        fp.end()
        ic.addPixmap(faded, QIcon.Disabled, QIcon.Off)
        ic.addPixmap(faded, QIcon.Disabled, QIcon.On)
        _icon_cache[name] = ic
    return _icon_cache[name]


def _gray(pm: QPixmap) -> QPixmap:
    """Bản xám của biểu tượng (giữ độ trong suốt) để mục bị khoá không còn màu nhấn."""
    img = pm.toImage().convertToFormat(QImage.Format_ARGB32)
    alpha = img.convertToFormat(QImage.Format_Alpha8)
    g = QImage(img.size(), QImage.Format_ARGB32)
    g.fill(QColor("#3c4654"))
    g.setAlphaChannel(alpha)
    return QPixmap.fromImage(g)


def _page(p, x=6.0, y=3.0, w=12.0, h=18.0, fold=4.0):
    _poly(p, [(x, y), (x + w - fold, y), (x + w, y + fold), (x + w, y + h), (x, y + h)], True)
    _poly(p, [(x + w - fold, y), (x + w - fold, y + fold), (x + w, y + fold)])


def _plus(p, cx, cy, r=3.0):
    p.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))
    p.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))


def _cross(p, cx, cy, r=2.6, color="#d93025"):
    pen = p.pen()
    p.setPen(QPen(QColor(color), 1.9, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(cx - r, cy - r), QPointF(cx + r, cy + r))
    p.drawLine(QPointF(cx - r, cy + r), QPointF(cx + r, cy - r))
    p.setPen(pen)


def _arrow(p, x1, y1, x2, y2, head=3.0, color=None):
    import math
    pen = p.pen()
    if color:
        p.setPen(QPen(QColor(color), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    a = math.atan2(y2 - y1, x2 - x1)
    for d in (2.5, -2.5):
        p.drawLine(QPointF(x2, y2), QPointF(x2 - head * math.cos(a + d / 4.2), y2 - head * math.sin(a + d / 4.2)))
    p.setPen(pen)


def _text(p, s, rect, size=7.5, color=None, bold=True):
    f = QFont()
    f.setPixelSize(int(size))
    f.setBold(bold)
    pen = p.pen()
    p.setFont(f)
    if color:
        p.setPen(QColor(color))
    p.drawText(QRectF(*rect), Qt.AlignCenter, s)
    p.setPen(pen)


def _ribbon(p, x=7.0, y=3.0, w=10.0, h=18.0):
    _poly(p, [(x, y), (x + w, y), (x + w, y + h), (x + w / 2, y + h - 4.5), (x, y + h)], True)


def _picture(p, x=3.0, y=5.0, w=18.0, h=14.0):
    p.drawRect(QRectF(x, y, w, h))
    _poly(p, [(x, y + h - 2), (x + w * 0.33, y + h * 0.45), (x + w * 0.56, y + h * 0.72), (x + w * 0.72, y + h * 0.5),
              (x + w, y + h - 2)])
    p.drawEllipse(QPointF(x + w * 0.72, y + h * 0.28), 1.1, 1.1)


def _shield(p):
    _poly(p, [(12, 3), (20, 6), (20, 13), (12, 21), (4, 13), (4, 6)], True)


def _doc_letter(letter, color):
    return lambda p: (_page(p, 4, 3, 13, 18), _text(p, letter, (4, 9, 13, 11), 9, color))


ICONS.update({
    "pdf": lambda p: (_page(p), _text(p, "PDF", (6, 10, 12, 9), 5.5, "#d93025")),
    "new": lambda p: (_page(p, 4, 3, 12, 18), _plus(p, 18.5, 17.5, 3)),
    "recent": lambda p: (p.drawEllipse(QPointF(12, 12), 8.5, 8.5), _poly(p, [(12, 7), (12, 12), (16, 14)])),
    "saveas": lambda p: (p.drawRoundedRect(QRectF(3, 3, 14, 14), 1.5, 1.5), p.drawRect(QRectF(6, 3, 6, 4)),
                         _poly(p, [(13, 21), (14, 17.5), (19.5, 12), (22, 14.5), (16.5, 20)], True)),
    "info": lambda p: (p.drawEllipse(QPointF(12, 12), 8.5, 8.5), p.drawLine(QPointF(12, 11), QPointF(12, 17)),
                       p.drawPoint(QPointF(12, 7.5))),
    "close": lambda p: (p.drawRoundedRect(QRectF(4, 4, 16, 16), 2, 2), _cross(p, 12, 12, 3.6, "#3c4654")),
    "exit": lambda p: (_poly(p, [(13, 4), (5, 4), (5, 20), (13, 20)]), _arrow(p, 10, 12, 20, 12, 3.5)),
    "copy": lambda p: (p.drawRoundedRect(QRectF(8, 8, 12, 13), 1.5, 1.5), _poly(p, [(16, 5), (16, 3.5), (4, 3.5), (4, 17), (5.5, 17)])),
    "saveimg": lambda p: (_picture(p, 3, 3, 15, 12), _arrow(p, 17, 13, 17, 21, 3.2, "#1a73e8")),
    "delimg": lambda p: (_picture(p, 3, 3, 15, 12), _cross(p, 17.5, 17.5, 3)),
    "search": lambda p: _mag(p),
    "guide": lambda p: (p.drawRoundedRect(QRectF(4, 3, 16, 18), 2, 2), p.drawLine(QPointF(8, 3), QPointF(8, 21)),
                        p.drawLine(QPointF(11, 8), QPointF(17, 8)), p.drawLine(QPointF(11, 12), QPointF(17, 12))),
    "listmenu": lambda p: ([p.drawRect(QRectF(3.5, y - 1.2, 2.4, 2.4)) for y in (6, 12, 18)],
                           [p.drawLine(QPointF(9, y), QPointF(21, y)) for y in (6, 12, 18)]),
    "collapseall": lambda p: (_poly(p, [(6, 11), (12, 6), (18, 11)], False), _poly(p, [(6, 19), (12, 14), (18, 19)], False)),
    "expandall": lambda p: (_poly(p, [(6, 5), (12, 10), (18, 5)], False), _poly(p, [(6, 13), (12, 18), (18, 13)], False)),
    "next": lambda p: (p.drawEllipse(QPointF(9, 9), 5.5, 5.5), p.drawLine(QPointF(13, 13), QPointF(16, 16)),
                       _poly(p, [(16.5, 16.5), (21, 19), (16.5, 21.5)])),
    "prev": lambda p: (p.drawEllipse(QPointF(15, 9), 5.5, 5.5), p.drawLine(QPointF(11, 13), QPointF(8, 16)),
                       _poly(p, [(7.5, 16.5), (3, 19), (7.5, 21.5)])),
    "delnote": lambda p: (p.drawRoundedRect(QRectF(3, 3, 15, 11), 2, 2), _poly(p, [(6, 14), (6, 18), (10, 14)]),
                          _cross(p, 18, 18, 3)),
    "flatten": lambda p: (_poly(p, [(12, 3), (21, 7.5), (12, 12), (3, 7.5)], True), _poly(p, [(3, 12), (12, 16.5), (21, 12)]),
                          p.drawLine(QPointF(3, 20.5), QPointF(21, 20.5))),
    "actual": lambda p: (p.drawRoundedRect(QRectF(2.5, 6, 19, 12), 2, 2), _text(p, "1:1", (2.5, 6, 19, 12), 8.5)),
    "fullscreen": lambda p: (_poly(p, [(4, 9), (4, 4), (9, 4)]), _poly(p, [(15, 4), (20, 4), (20, 9)]),
                             _poly(p, [(20, 15), (20, 20), (15, 20)]), _poly(p, [(9, 20), (4, 20), (4, 15)])),
    "extract": lambda p: (_page(p, 3, 3, 11, 18), _arrow(p, 11, 14, 21.5, 14, 3.5, "#1a73e8")),
    "duplicate": lambda p: (p.drawRect(QRectF(8, 7, 12, 14)), _poly(p, [(16, 4), (4, 4), (4, 18)]), _plus(p, 14, 14, 2.6)),
    "pageup": lambda p: (_page(p, 3, 3, 11, 18), _arrow(p, 19, 19, 19, 5, 3.5, "#1a73e8")),
    "pagedown": lambda p: (_page(p, 3, 3, 11, 18), _arrow(p, 19, 5, 19, 19, 3.5, "#1a73e8")),
    "addpage": lambda p: (_page(p, 3, 3, 11, 18), _plus(p, 19, 12, 3)),
    "insertfile": lambda p: (_page(p, 10, 3, 11, 18), _arrow(p, 2.5, 12, 13, 12, 3.5, "#1a73e8")),
    "pagenum": lambda p: (_page(p, 6, 3, 12, 18), _text(p, "1", (6, 11, 12, 10), 8.5)),
    "watermark": lambda p: (_page(p, 6, 3, 12, 18), _text(p, "W", (6, 8, 12, 12), 9, "#e98b8b")),
    "bookmark": lambda p: _ribbon(p),
    "bookmark_add": lambda p: (_ribbon(p, 4, 3, 10, 18), _plus(p, 19, 9, 3)),
    "bookmark_child": lambda p: (_ribbon(p, 10, 6, 9, 15), _poly(p, [(4, 3), (4, 10), (8, 10)])),
    "bookmarks": lambda p: (_ribbon(p, 3, 3, 7, 12), p.drawLine(QPointF(13, 5), QPointF(21, 5)),
                            p.drawLine(QPointF(13, 10), QPointF(21, 10)), p.drawLine(QPointF(13, 15), QPointF(21, 15)),
                            p.drawLine(QPointF(4, 20), QPointF(21, 20))),
    "bookmark_auto": lambda p: (_ribbon(p, 4, 5, 9, 16), _plus(p, 18.5, 6.5, 3.2),
                                p.drawLine(QPointF(16.3, 4.3), QPointF(20.7, 8.7)), p.drawLine(QPointF(16.3, 8.7), QPointF(20.7, 4.3))),
    "bookmark_pages": lambda p: (_page(p, 3, 3, 11, 18), _ribbon(p, 15, 6, 6.5, 12)),
    "bookmark_del": lambda p: (_ribbon(p, 4, 3, 10, 18), _cross(p, 19, 8, 3)),
    "word": _doc_letter("W", "#185abd"),
    "excel": _doc_letter("X", "#107c41"),
    "txt": lambda p: (_page(p, 5, 3, 13, 18), p.drawLine(QPointF(8, 10), QPointF(15, 10)),
                      p.drawLine(QPointF(8, 13.5), QPointF(15, 13.5)), p.drawLine(QPointF(8, 17), QPointF(13, 17))),
    "html": lambda p: (_poly(p, [(8, 7), (3, 12), (8, 17)]), _poly(p, [(16, 7), (21, 12), (16, 17)]),
                       p.drawLine(QPointF(13.5, 5), QPointF(10.5, 19))),
    "toimg": lambda p: (_picture(p, 8, 8, 14, 12), _poly(p, [(11, 4), (3, 4), (3, 16)]), _poly(p, [(11, 4), (11, 8)])),
    "topdf": lambda p: (_page(p, 9, 3, 12, 18), _text(p, "PDF", (9, 10, 12, 9), 5.5, "#d93025"),
                        _arrow(p, 1.5, 12, 8, 12, 3, "#1a73e8")),
    "imgs2pdf": lambda p: (_picture(p, 2.5, 9, 13, 11), _poly(p, [(6, 6.5), (6, 4.5), (19.5, 4.5), (19.5, 15), (17.5, 15)]),
                           _plus(p, 19.5, 19.5, 2.6)),
    "ocr": lambda p: (_poly(p, [(3, 8), (3, 4), (7, 4)]), _poly(p, [(17, 4), (21, 4), (21, 8)]),
                      _poly(p, [(21, 16), (21, 20), (17, 20)]), _poly(p, [(7, 20), (3, 20), (3, 16)]),
                      _text(p, "A", (5, 5, 14, 14), 11)),
    "compress": lambda p: (_arrow(p, 12, 2.5, 12, 9, 3.2), _arrow(p, 12, 21.5, 12, 15, 3.2),
                           p.drawLine(QPointF(4, 12), QPointF(20, 12))),
    "signhidden": lambda p: (_shield(p), p.drawLine(QPointF(5, 20), QPointF(19, 5))),
    "unlock": lambda p: (p.drawRoundedRect(QRectF(5, 11, 14, 10), 1.5, 1.5),
                         _path(p, [("M", 8, 11), ("L", 8, 8), ("C", 8, 2.5, 16, 2.5, 16, 7)])),
    "certfolder": lambda p: (_poly(p, [(3, 6), (9, 6), (11, 8.5), (21, 8.5), (21, 19), (3, 19)], True),
                             _poly(p, [(8.5, 13.5), (11, 16), (15.5, 11.5)])),
    "editnote": lambda p: (p.drawRoundedRect(QRectF(3, 3, 15, 11), 2, 2), _poly(p, [(6, 14), (6, 18), (10, 14)]),
                           _poly(p, [(13, 21), (14, 17.5), (19.5, 12), (22, 14.5), (16.5, 20)], True)),
    "retarget": lambda p: (p.drawEllipse(QPointF(12, 12), 7, 7), p.drawEllipse(QPointF(12, 12), 2, 2),
                           p.drawLine(QPointF(12, 2), QPointF(12, 6)), p.drawLine(QPointF(12, 18), QPointF(12, 22)),
                           p.drawLine(QPointF(2, 12), QPointF(6, 12)), p.drawLine(QPointF(18, 12), QPointF(22, 12))),
    "keys": lambda p: (p.drawRoundedRect(QRectF(2.5, 6, 19, 12), 2, 2), p.drawLine(QPointF(8, 15), QPointF(16, 15)),
                       p.drawPoint(QPointF(6.5, 10)), p.drawPoint(QPointF(10, 10)), p.drawPoint(QPointF(14, 10)),
                       p.drawPoint(QPointF(17.5, 10))),
    "translate": lambda p: (_text(p, "A", (1, 2, 11, 13), 11), p.drawEllipse(QPointF(16, 15), 6, 6),
                            p.drawLine(QPointF(10, 15), QPointF(22, 15)), p.drawEllipse(QPointF(16, 15), 2.6, 6)),
    "up": lambda p: _arrow(p, 12, 20, 12, 4, 4.5),
    "down": lambda p: _arrow(p, 12, 4, 12, 20, 4.5),
    "indent": lambda p: (_arrow(p, 3, 12, 11, 12, 3.5), p.drawLine(QPointF(14, 6), QPointF(21, 6)),
                         p.drawLine(QPointF(14, 12), QPointF(21, 12)), p.drawLine(QPointF(14, 18), QPointF(21, 18))),
    "outdent": lambda p: (_arrow(p, 11, 12, 3, 12, 3.5), p.drawLine(QPointF(14, 6), QPointF(21, 6)),
                          p.drawLine(QPointF(14, 12), QPointF(21, 12)), p.drawLine(QPointF(14, 18), QPointF(21, 18))),
})

# Mục menu -> tên biểu tượng (dò theo nội dung chữ của mục)
MENU_ICONS = {
    "Ghép nhiều ảnh thành một PDF…": "imgs2pdf", "PDF trắng mới": "new", "Mở gần đây": "recent", "Lưu thành…": "saveas",
    "Thông tin tài liệu": "info", "Đóng tab": "close", "Thoát": "exit",
    "Sao chép chữ / hình ảnh đang chọn": "copy", "Lưu hình ảnh đang chọn thành file…": "saveimg",
    "Xoá hình ảnh đang chọn khỏi trang": "delimg", "Tìm…": "search", "Tìm tiếp": "next", "Tìm ngược lại": "prev",
    "Xoá ghi chú/ảnh đang chọn": "delnote", "Làm phẳng ghi chú (gắn chết vào trang)": "flatten",
    "Kích thước thật (100%)": "actual", "Toàn màn hình": "fullscreen", "Bật/tắt cuộn đồng bộ khi so sánh": "syncscroll",
    "Trích trang đang chọn ra file mới…": "extract", "Nhân đôi trang": "duplicate", "Chuyển trang lên trước": "pageup",
    "Chuyển trang xuống sau": "pagedown", "Chèn trang trắng sau trang này": "addpage",
    "Chèn file khác vào sau trang này…": "insertfile", "Đánh số trang…": "pagenum",
    "Đóng dấu chìm (watermark)…": "watermark",
    "Thêm bookmark tại vị trí đang xem": "bookmark_add", "Thêm bookmark con của mục đang chọn": "bookmark_child",
    "Thêm bookmark con": "bookmark_child", "Hiện bảng bookmark": "bookmarks", "Ẩn bảng bookmark": "bookmarks",
    "Tự tạo bookmark từ các tiêu đề…": "bookmark_auto", "Tạo bookmark cho từng trang": "bookmark_pages",
    "Xoá tất cả bookmark": "bookmark_del",
    "Dịch tài liệu sang ngôn ngữ khác…": "translate", "Rà soát / sửa câu dịch của trang này…": "edittext", "PDF → Word (.docx)…": "word", "PDF → Excel (.xlsx)…": "excel", "PDF → Ảnh (PNG/JPG)…": "toimg",
    "PDF → Văn bản (.txt)…": "txt", "Xuất mọi hình ảnh trong PDF ra thư mục…": "saveimg", "PDF → HTML…": "html",
    "Ảnh / Word / Excel / PowerPoint → PDF…": "topdf", "Nhận dạng chữ (OCR) cho bản scan…": "ocr",
    "Nén giảm dung lượng…": "compress",
    "Ký số không hiện khung chữ ký…": "signhidden", "Gỡ mật khẩu": "unlock",
    "Mở thư mục chứng thư gốc tin cậy": "certfolder", "Giới thiệu": "info", "Danh sách phím tắt": "keys", "Hướng dẫn sử dụng": "guide",
    # menu chuột phải trong trang và trong bảng bookmark
    "Sao chép": "copy", "Tô sáng": "highlight", "Gạch chân": "underline", "Gạch ngang": "strike",
    "Sao chép hình ảnh": "copy", "Lưu hình ảnh thành file…": "saveimg", "Xoá hình ảnh khỏi trang": "delimg",
    "Sửa nội dung…": "editnote", "Xoá ghi chú/ảnh này": "delnote", "Sửa chữ gốc tại đây…": "edittext",
    "Công cụ bàn tay": "hand", "Công cụ chọn chữ / hình ảnh": "select",
    "Đổi tên": "edittext", "Trỏ lại về vị trí đang xem": "retarget", "Xoá": "delete", "Chuyển lên": "up",
    "Chuyển xuống": "down", "Thụt vào làm mục con": "indent", "Đưa ra ngoài một cấp": "outdent",
}
_ACCENT.update({"translate": "#1a73e8", "delimg": "#3c4654", "delnote": "#3c4654", "bookmark_del": "#3c4654", "unlock": "#3c4654",
                "signhidden": "#188038", "certfolder": "#188038", "bookmark_add": "#1a73e8", "bookmark": "#1a73e8"})


def icon_for(text: str) -> QIcon:
    name = MENU_ICONS.get(text.replace("&", ""))
    return icon(name) if name else QIcon()


def apply_menu_icons(menu) -> None:
    """Gắn biểu tượng cho mọi mục menu chưa có (kể cả menu con)."""
    for act in menu.actions():
        if act.isSeparator():
            continue
        sub = act.menu()
        if act.icon().isNull():
            ic = icon_for(act.text())
            if not ic.isNull():
                act.setIcon(ic)
        if sub is not None:
            apply_menu_icons(sub)


# ---------------------------------------------------------------- biểu tượng ứng dụng
def paint_app_icon(size: int = 256) -> QPixmap:
    """Biểu tượng PDF Editor Lite: ô vuông bo góc màu xanh, tờ giấy trắng gập góc có chữ PDF và cây bút chì cam."""
    from PySide6.QtGui import QFont, QLinearGradient
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.scale(size / 256, size / 256)
    g = QLinearGradient(0, 0, 256, 256)
    g.setColorAt(0, QColor("#3B82F6"))
    g.setColorAt(1, QColor("#1E3A8A"))
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawRoundedRect(QRectF(8, 8, 240, 240), 54, 54)
    # tờ giấy gập góc
    page = QPainterPath()
    page.moveTo(70, 44)
    page.lineTo(152, 44)
    page.lineTo(190, 82)
    page.lineTo(190, 204)
    page.quadTo(190, 212, 182, 212)
    page.lineTo(70, 212)
    page.quadTo(62, 212, 62, 204)
    page.lineTo(62, 52)
    page.quadTo(62, 44, 70, 44)
    p.setBrush(QColor(0, 0, 0, 40))
    p.drawPath(page.translated(4, 6))
    p.setBrush(QColor("#FFFFFF"))
    p.drawPath(page)
    fold = QPainterPath()
    fold.moveTo(152, 44)
    fold.lineTo(152, 74)
    fold.quadTo(152, 82, 160, 82)
    fold.lineTo(190, 82)
    fold.closeSubpath()
    p.setBrush(QColor("#BFDBFE"))
    p.drawPath(fold)
    # chữ PDF
    f = QFont("Arial")
    f.setPixelSize(46)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("#1D4ED8"))
    p.drawText(QRectF(62, 96, 128, 52), Qt.AlignCenter, "PDF")
    # các dòng chữ
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#93C5FD"))
    for y, w in ((158, 92), (176, 64)):
        p.drawRoundedRect(QRectF(80, y, w, 8), 4, 4)
    # bút chì (chỉnh sửa)
    p.save()
    p.translate(196, 196)
    p.rotate(-45)
    p.setBrush(QColor(0, 0, 0, 45))
    p.drawRoundedRect(QRectF(-58, -11, 104, 30), 8, 8)
    p.setBrush(QColor("#F59E0B"))
    p.drawRect(QRectF(-34, -15, 70, 30))
    p.setBrush(QColor("#FBBF24"))
    p.drawRect(QRectF(-34, -15, 70, 10))
    p.setBrush(QColor("#F87171"))
    p.drawRoundedRect(QRectF(36, -15, 20, 30), 6, 6)
    p.setBrush(QColor("#E5E7EB"))
    p.drawRect(QRectF(30, -15, 9, 30))
    tip = QPolygonF([QPointF(-34, -15), QPointF(-62, 0), QPointF(-34, 15)])
    p.setBrush(QColor("#FDE68A"))
    p.drawPolygon(tip)
    p.setBrush(QColor("#1F2937"))
    p.drawPolygon(QPolygonF([QPointF(-52, -5.4), QPointF(-62, 0), QPointF(-52, 5.4)]))
    p.restore()
    p.end()
    return pm


def app_icon() -> QIcon:
    ic = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(paint_app_icon(s))
    return ic
