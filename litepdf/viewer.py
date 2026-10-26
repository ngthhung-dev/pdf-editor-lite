"""Mô hình tài liệu và khung xem/chỉnh sửa trang PDF."""
from __future__ import annotations

import bisect
import math
import time
import os
import shutil
import tempfile
from contextlib import contextmanager

import pymupdf
from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (QColor, QDesktopServices, QGuiApplication, QImage, QPainter, QPen, QPolygonF,
                           QTransform)
from PySide6.QtWidgets import QApplication, QGraphicsScene, QGraphicsView, QInputDialog, QMenu, QMessageBox, QToolTip

from . import tools
from .icons import icon, icon_for

GAP = 14.0
MARGIN = 16.0
MAX_PIXELS = 16_000_000
MOVABLE = {"Square", "Circle", "Stamp", "Text", "FreeText"}
MARK_TOOLS = {"highlight", "underline", "strike"}
DRAG_TOOLS = {"rect", "ellipse", "line", "arrow", "image", "erase", "sign"}
ONE_SHOT = {"image", "sign", "text", "note"}


def qcolor_to_rgb(c: QColor) -> tuple[float, float, float]:
    return (c.redF(), c.greenF(), c.blueF())


def _user_name() -> str:
    try:
        import getpass
        return getpass.getuser()
    except Exception:
        return ""


INCR_MIN = int(os.environ.get("LITEPDF_INCR_MIN", 4_000_000))   # file từ cỡ này trở lên dùng cách hoàn tác "nối đuôi"
_work_root: str | None = None


def _work_dir() -> str:
    """Thư mục chứa bản làm việc tạm của các tài liệu lớn (xoá khi đóng tài liệu / thoát app)."""
    global _work_root
    if _work_root is None:
        import atexit
        import time as _t
        base = os.path.join(tempfile.gettempdir(), "PDFEditorLite-work")
        os.makedirs(base, exist_ok=True)
        try:        # dọn phần sót lại của những lần app bị tắt đột ngột
            for name in os.listdir(base):
                d = os.path.join(base, name)
                if os.path.isdir(d) and _t.time() - os.path.getmtime(d) > 2 * 86400:
                    shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass
        _work_root = tempfile.mkdtemp(prefix="p%d-" % os.getpid(), dir=base)
        atexit.register(lambda: shutil.rmtree(_work_root, ignore_errors=True))
    return _work_root


class DocModel(QObject):
    """Tài liệu PDF đang mở, có hoàn tác/làm lại.

    Hai cách giữ điểm hoàn tác:
    - File nhỏ: chụp lại cả tài liệu vào bộ nhớ trước mỗi thao tác (đơn giản, tốn vài ms).
    - File lớn (từ INCR_MIN): tài liệu được mở từ một bản làm việc tạm trên đĩa; sau mỗi thao tác chỉ phần thay đổi
      được ghi nối vào cuối file (PDF cho phép lưu "nối đuôi"). Điểm hoàn tác chỉ là độ dài file trước thao tác:
      hoàn tác = cắt file về độ dài đó rồi mở lại; làm lại = nối lại đúng đoạn đuôi đã cắt. Mỗi thao tác mất vài chục ms
      dù file hàng trăm MB, thay vì phải chép lại cả file. Lưu ý: sau mỗi thao tác `self.doc` là một đối tượng MỚI
      (mở lại từ file), nên mã bên ngoài không được giữ doc / page / annot cũ qua một lần sửa: luôn lấy lại từ model.doc.
    Một mục trong ngăn hoàn tác là: bytes (ảnh chụp cả tài liệu) | ("w", file, độ dài) | ("t", file, độ dài, đuôi)."""
    changed = Signal(object, bool)  # (chỉ số trang hoặc None, cấu trúc trang thay đổi)
    stateChanged = Signal()

    def __init__(self, data: bytes, path: str | None = None, password: str | None = None,
                 title: str | None = None, parent=None):
        super().__init__(parent)
        self.doc, self.encrypted = tools.open_pdf_bytes(data, password)
        self.security = tools.security_info(data, password) if self.encrypted else {}
        self.base_data: bytes | None = data  # đúng với nội dung trên đĩa khi chưa sửa
        self.path = path
        self.password = password if self.encrypted else None
        self.title = title or (os.path.basename(path) if path else "Chưa đặt tên.pdf")
        self.dirty = path is None
        self.fonts_added = False
        self.undo_stack: list = []
        self.redo_stack: list = []
        self._work: list | None = None          # [file tạm, độ dài hiện tại] khi đang dùng cách "nối đuôi"
        self._files: list[str] = []
        # File lớn: bản làm việc trên đĩa chỉ được tạo ở lần sửa đầu tiên, để mở file (chỉ xem) không phải chép cả file
        # ra thư mục tạm và mở lại lần nữa. File có mật khẩu: không bao giờ ghi bản đã giải mã ra đĩa.
        self._lazy = not self.encrypted and len(data) >= INCR_MIN

    # -- truy cập
    @property
    def page_count(self) -> int:
        return self.doc.page_count

    def page(self, i: int, for_edit: bool = False):
        return self.doc[i]

    # -- bản làm việc trên đĩa (file lớn)
    def _start_work(self, data: bytes) -> bool:
        """Chuyển tài liệu hiện tại (đúng bằng `data`) sang mở từ file tạm. Không hợp thì giữ nguyên cách cũ."""
        if len(data) < INCR_MIN:
            return False
        path = None
        try:
            fd, path = tempfile.mkstemp(suffix=".pdf", dir=_work_dir())
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            doc = pymupdf.open(path)
            if doc.needs_pass or doc.is_encrypted or not doc.can_save_incrementally():
                doc.close()
                raise ValueError("không lưu nối đuôi được")
        except Exception:
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass
            return False
        try:
            self.doc.close()
        except Exception:
            pass
        self.doc = doc
        self._work = [path, len(data)]
        self._files.append(path)
        return True

    def _commit(self) -> bool:
        """Ghi phần vừa thay đổi nối vào cuối bản làm việc."""
        path = self._work[0]
        try:
            self.doc.saveIncr()
        except Exception:
            return False
        # Mở lại tài liệu từ chính file vừa ghi. Bắt buộc: nếu giữ nguyên tài liệu đang mở, lần ghi sau thư viện sẽ ghi đè
        # lên phần đuôi của lần này (nó luôn ghi lại mọi thay đổi kể từ lúc mở), khi đó không cắt về đúng điểm này được.
        try:
            size = os.path.getsize(path)
            doc = pymupdf.open(path)
        except Exception:
            self._work = None                    # tài liệu đang mở vẫn dùng được; từ đây chụp cả tài liệu như file nhỏ
            return True
        try:
            self.doc.close()
        except Exception:
            pass
        self.doc = doc
        self._work[1] = size
        return True

    def _prefix(self, path: str, length: int) -> bytes:
        with open(path, "rb") as f:
            return f.read(length)

    def _open_work(self, path: str, length: int, tail: bytes = b"") -> None:
        """Mở tài liệu ở trạng thái: `length` byte đầu của file (+ đoạn đuôi nối thêm, nếu có)."""
        try:
            self.doc.close()
        except Exception:
            pass
        try:
            if os.path.getsize(path) != length:
                os.truncate(path, length)
            if tail:
                with open(path, "ab") as f:
                    f.write(tail)
            self.doc = pymupdf.open(path)
            self._work = [path, length + len(tail)]
        except Exception:
            # Không cắt/nối được file tạm (bị chương trình khác giữ...): dựng đúng trạng thái đó trong bộ nhớ
            self._work = None
            self.doc = pymupdf.open(stream=self._prefix(path, length) + tail, filetype="pdf")

    def _snapshot(self):
        """Điểm hoàn tác của trạng thái hiện tại."""
        if self._work:
            return ("w", self._work[0], self._work[1])
        if self._lazy and self.base_data is not None:      # chưa sửa gì: đúng bằng nội dung lúc mở, khỏi chụp lại
            return self.base_data
        return self.doc.tobytes()

    def _begin_work_after_edit(self) -> None:
        """Lần sửa đầu tiên của file lớn: từ đây chuyển sang bản làm việc trên đĩa (hoàn tác kiểu nối đuôi)."""
        if self._lazy:
            self._lazy = False
            try:
                self._start_work(self.doc.tobytes())
            except Exception:
                pass

    @staticmethod
    def _weight(e) -> int:
        return len(e) if isinstance(e, bytes) else (len(e[3]) if e[0] == "t" else 0)

    def _push(self, stack: list, snap, page=None, structure: bool = True) -> None:
        """Mỗi mục trong ngăn: (điểm hoàn tác, trang bị đụng tới, có đổi cấu trúc trang không). Hai thông tin sau để khi
        hoàn tác chỉ phải vẽ lại đúng trang đó, không dựng lại cả tài liệu."""
        stack.append((snap, page, structure))
        big = self._weight(snap) > 60_000_000
        while len(stack) > (3 if big else 200) or \
                (len(stack) > 2 and sum(self._weight(e[0]) for e in stack) > 400_000_000):
            stack.pop(0)

    def _reopen(self, snap) -> None:
        """Đưa tài liệu về trạng thái `snap` (không ghi nhận gì vào ngăn hoàn tác)."""
        if isinstance(snap, bytes):
            try:
                self.doc.close()
            except Exception:
                pass
            self._work = None
            self.doc = pymupdf.open(stream=snap, filetype="pdf")
        elif snap[0] == "w":
            self._open_work(snap[1], snap[2])
        else:
            self._open_work(snap[1], snap[2], snap[3])

    def _switch(self, target):
        """Chuyển sang trạng thái `target`; trả về mục để quay lại trạng thái vừa rời."""
        cur = self._work
        if not isinstance(target, bytes) and cur and target[1] == cur[0] and target[0] == "w" and target[2] < cur[1]:
            with open(cur[0], "rb") as f:        # cùng một file: giữ lại đoạn đuôi sắp cắt để còn làm lại được
                f.seek(target[2])
                left = ("t", cur[0], target[2], f.read(cur[1] - target[2]))
        elif not isinstance(target, bytes) and target[0] == "t":
            left = ("w", target[1], target[2])
        else:
            left = self._snapshot()
        self._reopen(target)
        return left

    @contextmanager
    def edit(self, page: int | None = None, structure: bool = False):
        """Bọc một thao tác sửa: tự lưu điểm hoàn tác, lỗi thì trả tài liệu về như cũ."""
        snap = self._snapshot()
        try:
            yield
        except Exception:
            self._reopen(snap)
            self.changed.emit(None, True)
            raise
        if isinstance(page, int):
            try:
                tools.style_notes(self.doc[page])      # ghi chú vừa tạo/sửa: dùng biểu tượng bong bóng thay cho ô vuông mặc định
            except Exception:
                pass
        if self._lazy:
            self._begin_work_after_edit()
        elif self._work and not self._commit():
            # không ghi nối đuôi được: từ đây quay về cách chụp cả tài liệu, điểm hoàn tác lấy từ phần file chưa đụng tới
            snap = self._prefix(snap[1], snap[2])
            self._work = None
        self._push(self.undo_stack, snap, page, structure)
        self.redo_stack.clear()
        self.dirty = True
        self.changed.emit(page, structure)
        self.stateChanged.emit()

    def replace_document(self, data: bytes) -> None:
        """Thay toàn bộ tài liệu (nén, OCR...) như một thao tác có thể hoàn tác."""
        snap = self._snapshot()
        try:
            self.doc.close()
        except Exception:
            pass
        self._work = None
        self._lazy = False
        self.doc = pymupdf.open(stream=data, filetype="pdf")
        if not self.encrypted:
            self._start_work(data)
        self._push(self.undo_stack, snap)
        self.redo_stack.clear()
        self.dirty = True
        self.changed.emit(None, True)
        self.stateChanged.emit()

    def undo(self) -> bool:
        if not self.undo_stack:
            return False
        snap, page, structure = self.undo_stack.pop()
        self._push(self.redo_stack, self._switch(snap), page, structure)
        self.dirty = True
        self.changed.emit(page, structure)
        self.stateChanged.emit()
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            return False
        snap, page, structure = self.redo_stack.pop()
        self._push(self.undo_stack, self._switch(snap), page, structure)
        self.dirty = True
        self.changed.emit(page, structure)
        self.stateChanged.emit()
        return True

    def export_bytes(self) -> bytes:
        """Bytes PDF hiện tại (không mã hoá). Chưa sửa gì thì trả đúng file gốc để giữ chữ ký số."""
        if not self.dirty and self.base_data is not None and not self.encrypted:
            return self.base_data
        if self.fonts_added:
            tools.finalize_fonts(self.doc)
        return self.doc.tobytes(garbage=3, deflate=True)

    def save(self, path: str) -> None:
        if self.fonts_added:
            tools.finalize_fonts(self.doc)
        d = os.path.dirname(os.path.abspath(path))
        try:      # ghi ra file tạm cạnh file đích rồi đổi tên: mất điện giữa chừng cũng không hỏng file cũ
            fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=d)
            os.close(fd)
            beside = True
        except OSError:
            # Thư mục đích không cho tạo file tạm (thư mục được Windows bảo vệ, ổ mạng, OneDrive...):
            # ghi ra thư mục tạm của hệ thống rồi chép thẳng vào file đích.
            fd, tmp = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            beside = False
        try:
            if self.password:
                tools.save_encrypted(self.doc, tmp, self.password, allow_edit=True)
            else:
                self.doc.save(tmp, garbage=3, deflate=True)
            if beside:
                os.replace(tmp, path)
            else:
                with open(tmp, "rb") as src, open(path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        finally:
            try:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            except OSError:
                pass
        with open(path, "rb") as f:
            self.base_data = f.read()
        self.path = path
        self.title = os.path.basename(path)
        self.dirty = False
        self.stateChanged.emit()

    def close(self):
        try:
            self.doc.close()
        except Exception:
            pass
        for f in self._files:
            try:
                os.unlink(f)
            except OSError:
                pass
        self._files = []
        self._work = None


# Tự nhận dạng chữ (OCR ngầm bằng Tesseract) cho trang không có chữ thật, như Edge / Chrome / Acrobat:
# chỉ để chọn, sao chép và tìm kiếm ngay trong app, không ghi gì vào file. App đặt "lang" theo lựa chọn OCR gần nhất.
AUTO_OCR = {"on": True, "lang": None, "max_search_pages": 60}


def _auto_ocr_lang():
    langs = tools.tess_languages()
    if not langs:
        return None
    want = AUTO_OCR.get("lang")
    if want and set(want.split("+")) <= set(langs):
        return want
    return "vie+eng" if {"vie", "eng"} <= set(langs) else "+".join(langs[:2])


class Viewer(QGraphicsView):
    pageChanged = Signal(int)
    zoomChanged = Signal(float)
    message = Signal(str)
    signRequested = Signal(int, object)  # trang, pymupdf.Rect
    toolChanged = Signal(str)
    selectionChanged = Signal()
    searchChanged = Signal(str)            # nhãn kết quả tìm đổi trong lúc dò tiếp ở nền

    def __init__(self, model: DocModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.setScene(QGraphicsScene(self))
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.setResizeAnchor(QGraphicsView.NoAnchor)
        self.setMouseTracking(True)
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAcceptDrops(False)
        self.bg = QColor("#dfe3e8")
        self.base = self.logicalDpiX() / 72.0
        self.zoom = 1.0
        self.fit = None  # mở file ở đúng 100% kích thước trang
        self.rects: list[QRectF] = []
        self.tops: list[float] = []
        self.cache: dict[int, tuple[float, QImage]] = {}
        self.words: dict[int, list] = {}
        self.ocr_done: set[int] = set()          # trang đã tự nhận dạng chữ (đã thử, có hay không có kết quả)
        self.ocr_found: set[int] = set()         # trong đó: trang có chữ nhận dạng được
        self.imgs: dict[int, list] = {}
        self.notes: dict[int, list] = {}     # ghi chú có nội dung trên từng trang (để hiện khi rê chuột)
        self._note_tip = None
        self.sel_image = None      # (trang, thông tin ảnh) khi đang chọn một hình ảnh gốc
        self.img_drag = None       # đang dời / co giãn / xoay ảnh đang chọn
        self.dicts: dict[int, dict] = {}
        self.tool = "hand"
        self.payload = None
        self.colors = {"mark": QColor("#ffe100"), "draw": QColor("#e02020"), "text": QColor("#000000")}
        self.line_width = 1.5
        self.font_size = 12.0
        self._cur_page = 0
        # trạng thái tương tác
        self.press = None          # QPointF (scene)
        self.press_page = None
        self.cur = None
        self.pan = None
        self.ink: list[QPointF] = []
        self.sel_page = None
        self.sel_rects: list[pymupdf.Rect] = []
        self.sel_text = ""
        self.hits: list[tuple[int, pymupdf.Rect]] = []
        self.hit_pages: list[int] = []         # số trang của từng kết quả (song song với hits), để tra nhanh
        self.diff_marks: dict[int, list] = {}  # so sánh hai tài liệu: trang -> các khung chữ khác với bên kia
        self.diff_pages: set[int] = set()      # các trang chỉ có ở bên này
        self.diff_gaps: dict[int, list] = {}   # trang -> vị trí mà bên kia có thêm chữ còn bên này thì không
        self.diff_rgb = (234, 67, 53)
        self.diff_focus = None                 # (trang, [khung]) của chỗ khác nhau đang xem
        self._scan: list[int] = []
        self._scan_pos = 0
        self._search_timer = QTimer(self, interval=0, timeout=self._search_tick)
        self.hit_idx = -1
        self.query = ""
        self.annot = None          # (trang, xref, loại)
        self.annot_rect = None     # pymupdf.Rect (đang hiển thị, kể cả khi kéo)
        self.annot_mode = None     # 'move' | 'resize'
        self.annot_off = None
        self.annot_moved = False
        self.drag_run = None
        self.font_family = "arial"
        self.hover_run = None
        self._rerender = QTimer(self, singleShot=True, interval=140, timeout=self._do_rerender)
        self._lazy = QTimer(self, singleShot=True, interval=70, timeout=self._do_rerender)
        self._render_at, self._render_paint, self._paint_no = 0.0, -1, 0
        self.last_scroll = 0.0
        model.changed.connect(self._on_changed)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self.layout_pages()

    # ------------------------------------------------------------ bố cục
    def layout_pages(self):
        doc = self.model.doc
        sizes = []
        self.rot = []  # (góc xoay, ma trận hiển thị, ma trận ngược, khung trang chưa xoay)
        for p in doc:
            sizes.append((p.rect.width, p.rect.height))
            ub = p.rect * p.derotation_matrix
            ub.normalize()
            self.rot.append((p.rotation, p.rotation_matrix, p.derotation_matrix, ub))
        maxw = max((w for w, _ in sizes), default=595)
        self.rects, self.tops = [], []
        y = MARGIN
        for w, h in sizes:
            self.rects.append(QRectF((maxw - w) / 2 + MARGIN, y, w, h))
            self.tops.append(y)
            y += h + GAP
        self.scene().setSceneRect(0, 0, maxw + 2 * MARGIN, max(y - GAP + MARGIN, 10))
        self.cache.clear()
        self.words.clear()
        self.ocr_done.clear()
        self.ocr_found.clear()
        self.imgs.clear()
        self.notes.clear()
        self.dicts.clear()
        self.viewport().update()

    def _on_changed(self, page, structure):
        if page == "toc":  # chỉ bookmark thay đổi, trang không đổi
            return
        self.sel_image = None
        self.sel_rects, self.sel_text, self.hover_run = [], "", None
        if structure or page is None:
            self.annot = None
            self._reset_search()                 # trang đã đổi: kết quả tìm cũ không còn đúng, lần tìm sau dò lại
            v = self.verticalScrollBar().value()
            self.layout_pages()
            self.apply_zoom()
            self.verticalScrollBar().setValue(v)
        else:
            if self.query:                       # trang vừa sửa: bỏ kết quả tìm cũ của trang đó, lần tìm sau dò lại
                keep = [h for h in self.hits if h[0] != page]
                self._search_timer.stop()
                self.hits, self.hit_pages, self.hit_idx, self.query = keep, [h[0] for h in keep], -1, ""
                self._scan, self._scan_pos = [], 0
            self.cache.pop(page, None)
            self.words.pop(page, None)
            self.ocr_done.discard(page)
            self.ocr_found.discard(page)
            self.imgs.pop(page, None)
            self.notes.pop(page, None)
            self.dicts.pop(page, None)
            if page < len(self.rects):
                r = self.model.doc[page].rect
                if abs(r.width - self.rects[page].width()) > 0.5 or abs(r.height - self.rects[page].height()) > 0.5:
                    self.layout_pages()
        self.viewport().update()

    # ------------------------------------------------------------ thu phóng
    def apply_zoom(self):
        if not self.rects:
            return
        vw = self.viewport().width() - 2
        vh = self.viewport().height() - 2
        sw = self.scene().sceneRect().width()
        if self.fit == "width":
            self.zoom = max(0.1, vw / (sw * self.base))
        elif self.fit == "page":
            r = self.rects[min(self._cur_page, len(self.rects) - 1)]
            self.zoom = max(0.1, min(vw / ((r.width() + 2 * MARGIN) * self.base),
                                     vh / ((r.height() + 2 * MARGIN) * self.base)))
        self.zoom = min(max(self.zoom, 0.1), 6.0)
        s = self.zoom * self.base
        self.resetTransform()
        self.scale(s, s)
        self.zoomChanged.emit(self.zoom)
        self.viewport().update()

    def set_zoom(self, z: float, anchor: QPointF | None = None):
        self.fit = None
        vp = anchor if anchor is not None else QPointF(self.viewport().width() / 2, self.viewport().height() / 2)
        before = self.mapToScene(vp.toPoint())
        self.zoom = z
        self.apply_zoom()
        after = self.mapToScene(vp.toPoint())
        d = (after - before) * self.transform().m11()
        self.horizontalScrollBar().setValue(int(self.horizontalScrollBar().value() - d.x()))
        self.verticalScrollBar().setValue(int(self.verticalScrollBar().value() - d.y()))

    def set_fit(self, mode: str):
        page = self._cur_page
        self.fit = mode
        self.apply_zoom()
        if mode == "page":
            self.goto_page(page)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.fit:
            self.apply_zoom()

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            f = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
            self.set_zoom(self.zoom * f, e.position())
            e.accept()
        else:
            super().wheelEvent(e)

    # ------------------------------------------------------------ điều hướng
    def current_page(self) -> int:
        return self._cur_page

    def _on_scroll(self, *_):
        if not self.rects:
            return
        self.last_scroll = time.perf_counter()
        y = self.mapToScene(0, int(self.viewport().height() * 0.35)).y()
        i = max(0, min(bisect.bisect_right(self.tops, y) - 1, len(self.rects) - 1))
        if i != self._cur_page:
            self._cur_page = i
            self.pageChanged.emit(i)

    def goto_page(self, i: int, y: float = 0.0):
        if not self.rects:
            return
        i = max(0, min(i, len(self.rects) - 1))
        r = self.rects[i]
        top = (r.top() + y - GAP / 2) * self.transform().m11()
        self.verticalScrollBar().setValue(int(top))
        if self._cur_page != i:
            self._cur_page = i
            self.pageChanged.emit(i)

    def ensure_visible(self, page: int, rect: pymupdf.Rect):
        sr = self.to_scene(page, rect)
        vis = self.mapToScene(self.viewport().rect()).boundingRect()
        if not vis.contains(sr):
            self.centerOn(sr.center())

    # ------------------------------------------------------------ toạ độ
    def page_at(self, sp: QPointF, clamp: bool = True) -> int | None:
        if not self.rects:
            return None
        i = max(0, min(bisect.bisect_right(self.tops, sp.y()) - 1, len(self.rects) - 1))
        if not clamp and not self.rects[i].contains(sp):
            return None
        return i

    def to_page(self, i: int, sp: QPointF, clamp: bool = True) -> pymupdf.Point:
        r = self.rects[i]
        x, y = sp.x() - r.left(), sp.y() - r.top()
        if clamp:
            x = min(max(x, 0.0), r.width())
            y = min(max(y, 0.0), r.height())
        p = pymupdf.Point(x, y)
        return p * self.rot[i][2] if self.rot[i][0] else p

    def to_display(self, i: int, pt) -> pymupdf.Point:
        p = pymupdf.Point(pt)
        return p * self.rot[i][1] if self.rot[i][0] else p

    def to_scene(self, i: int, rect) -> QRectF:
        """Khung trên trang (toạ độ trang chưa xoay, như PyMuPDF dùng) -> khung trên màn hình."""
        r = self.rects[i]
        rect = pymupdf.Rect(rect)
        if self.rot[i][0]:
            rect = rect * self.rot[i][1]
            rect.normalize()
        return QRectF(r.left() + rect.x0, r.top() + rect.y0, rect.width, rect.height)

    # ------------------------------------------------------------ kết xuất
    def _render(self, i: int, want: float) -> QImage:
        page = self.model.doc[i]
        r = page.rect
        sc = min(want, math.sqrt(MAX_PIXELS / max(1.0, r.width * r.height)))
        try:
            tools.style_notes(page)      # ghi chú cũ của app (ô vuông thô) cũng được vẽ bằng biểu tượng mới
            pix = page.get_pixmap(matrix=pymupdf.Matrix(sc, sc), alpha=False, annots=True)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
        except Exception:
            img = QImage(8, 8, QImage.Format_RGB888)
            img.fill(Qt.white)
        self.cache[i] = (want, img, sc == want)
        if len(self.cache) > 10 or sum(v[1].sizeInBytes() for v in self.cache.values()) > 220_000_000:
            for k in sorted(self.cache, key=lambda k: -abs(k - i))[:max(1, len(self.cache) - 5)]:
                if k != i:
                    del self.cache[k]
        return img

    def _visible(self, rect: QRectF) -> range:
        if not self.rects:
            return range(0)
        a = max(0, bisect.bisect_right(self.tops, rect.top()) - 1)
        b = min(len(self.rects), bisect.bisect_right(self.tops, rect.bottom()))
        return range(a, b)

    def _do_rerender(self):
        doc = self.model.doc
        if doc is None or getattr(doc, "is_closed", False):
            return
        want = round(self.transform().m11() * self.devicePixelRatioF(), 3)
        vis = self.mapToScene(self.viewport().rect()).boundingRect()
        for i in self._visible(vis):
            if i not in self.cache or self.cache[i][0] != want:
                self._render(i, want)
        self.viewport().update()

    def drawBackground(self, p: QPainter, rect: QRectF):
        p.fillRect(rect, self.bg)
        self._paint_no += 1
        s = self.transform().m11()
        want = round(s * self.devicePixelRatioF(), 3)
        for i in self._visible(rect):
            r = self.rects[i]
            p.fillRect(r.translated(1.6 / s, 1.6 / s), QColor(0, 0, 0, 45))
            ent = self.cache.get(i)
            if ent is None:
                # Đang kéo thanh cuộn lướt qua nhiều trang: không dựng từng trang lướt qua (mỗi trang mất vài chục ms,
                # dựng hết thì cửa sổ khựng). Vẽ tạm trang trắng, dừng tay một nhịp mới dựng cho nét.
                now = time.perf_counter()
                if self._paint_no != self._render_paint and now - self._render_at < 0.1:
                    p.fillRect(r, Qt.white)
                    self._lazy.start()
                    continue
                self._render(i, want)
                self._render_at, self._render_paint = time.perf_counter(), self._paint_no
                ent = self.cache[i]
            img = ent[1]
            stale = ent[0] != want
            if stale:
                self._rerender.start()
            if not stale and ent[2]:
                # Ảnh đã kết xuất đúng độ phân giải màn hình: vẽ 1:1, canh đúng điểm ảnh vật lý để chữ sắc nét
                # (kể cả khi Windows đặt tỉ lệ hiển thị 125% / 150%).
                dpr = self.devicePixelRatioF()
                pt = p.worldTransform().map(r.topLeft())
                p.save()
                p.resetTransform()
                p.setRenderHint(QPainter.SmoothPixmapTransform, False)
                p.drawImage(QRectF(round(pt.x() * dpr) / dpr, round(pt.y() * dpr) / dpr,
                                   img.width() / dpr, img.height() / dpr), img)
                p.restore()
            else:  # đang đổi mức phóng: tạm kéo giãn ảnh cũ, lát sau kết xuất lại cho nét
                p.setRenderHint(QPainter.SmoothPixmapTransform, True)
                p.drawImage(r, img)

    def drawForeground(self, p: QPainter, rect: QRectF):
        s = self.transform().m11()
        px = 1.0 / s
        p.setRenderHint(QPainter.Antialiasing, True)
        # kết quả tìm kiếm
        if self.hits:                            # chỉ vẽ kết quả của các trang đang hiện (tài liệu có thể có hàng nghìn kết quả)
            vis = self._visible(rect)
            lo = bisect.bisect_left(self.hit_pages, vis.start)
            hi = bisect.bisect_left(self.hit_pages, vis.stop)
            for k in range(lo, hi):
                pg, r = self.hits[k]
                if pg < len(self.rects):
                    p.fillRect(self.to_scene(pg, r),
                               QColor(255, 140, 0, 130) if k == self.hit_idx else QColor(255, 235, 0, 90))
        # chỗ khác nhau giữa hai tài liệu đang so sánh
        if self.diff_marks or self.diff_pages or self.diff_gaps:
            for i in self._visible(rect):
                if i in self.diff_pages:         # cả trang chỉ có ở bên này: viền và phủ nhẹ cả trang
                    r = self.rects[i]
                    p.fillRect(r, QColor(self.diff_rgb[0], self.diff_rgb[1], self.diff_rgb[2], 28))
                    p.setPen(QPen(QColor(*self.diff_rgb), 3 * px))
                    p.setBrush(Qt.NoBrush)
                    p.drawRect(r)
                for r in self.diff_marks.get(i, ()):
                    p.fillRect(self.to_scene(i, r).adjusted(-px, -px, px, px),
                               QColor(self.diff_rgb[0], self.diff_rgb[1], self.diff_rgb[2], 85))
                for r in self.diff_gaps.get(i, ()):       # bên kia có thêm chữ ở đây, bên này không có: vạch đánh dấu chỗ thiếu
                    sr = self.to_scene(i, r)
                    p.fillRect(QRectF(sr.left() - 3.5 * px, sr.top() - 2 * px, 3 * px, sr.height() + 4 * px),
                               QColor(255, 140, 0, 230))
            if self.diff_focus and self.diff_focus[0] < len(self.rects):
                p.setPen(QPen(QColor(255, 140, 0), 2.2 * px))
                p.setBrush(Qt.NoBrush)
                for r in self.diff_focus[1]:
                    p.drawRect(self.to_scene(self.diff_focus[0], r).adjusted(-2 * px, -2 * px, 2 * px, 2 * px))
        # vùng chữ đang chọn
        if self.sel_page is not None and self.sel_page < len(self.rects):
            for r in self.sel_rects:
                p.fillRect(self.to_scene(self.sel_page, r), QColor(40, 110, 255, 80))
        # hình ảnh đang chọn
        if self.sel_image and self.sel_image[0] < len(self.rects) and self.img_drag is None:
            si, sinfo = self.sel_image
            sr = self.to_scene(si, sinfo["bbox"])
            p.setPen(QPen(QColor("#1a73e8"), 2 * px))
            p.setBrush(QColor(26, 115, 232, 30))
            p.drawRect(sr)
            if self.tool == "select" and not self.rot[si][0]:
                h = 4.5 * px
                r = pymupdf.Rect(sinfo["bbox"])
                p.setPen(QPen(QColor("#1a73e8"), 1.2 * px))
                p.setBrush(Qt.white)
                for c in (r.tl, r.tr, r.bl, r.br):          # tay nắm đổi cỡ ở 4 góc
                    q = self._spt(si, c)
                    p.drawRect(QRectF(q.x() - h, q.y() - h, 2 * h, 2 * h))
                if not sinfo.get("annot"):                   # tay nắm xoay phía trên
                    top = self._spt(si, pymupdf.Point((r.x0 + r.x1) / 2, r.y0))
                    rh = self._img_rot_handle(si, r)
                    p.drawLine(top, rh)
                    p.setBrush(QColor("#1a73e8"))
                    p.drawEllipse(rh, h * 1.15, h * 1.15)
        if self.img_drag is not None:
            d = self.img_drag
            i0, r = d["i"], pymupdf.Rect(d["info"]["bbox"])
            p.fillRect(self.to_scene(i0, r), QColor(255, 255, 255, 170))       # chỗ cũ mờ đi
            qd = r.quad * d["A"]
            poly = QPolygonF([self._spt(i0, qd.ul), self._spt(i0, qd.ur), self._spt(i0, qd.lr), self._spt(i0, qd.ll)])
            pm = d.get("pix")
            if pm is not None and not pm.isNull():
                from PySide6.QtGui import QTransform
                src = QPolygonF([QPointF(0, 0), QPointF(pm.width(), 0), QPointF(pm.width(), pm.height()),
                                 QPointF(0, pm.height())])
                t = QTransform()
                if QTransform.quadToQuad(src, poly, t):
                    p.save()
                    p.setTransform(t, True)
                    p.setOpacity(0.75)
                    p.drawPixmap(0, 0, pm)
                    p.restore()
            p.setPen(QPen(QColor("#1a73e8"), 1.4 * px, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawPolygon(poly)
        # chữ gốc dưới con trỏ (công cụ sửa chữ)
        if self.tool == "edittext" and self.hover_run:
            pg, run = self.hover_run
            p.setPen(QPen(QColor("#1a73e8"), 1.2 * px, Qt.DashLine))
            p.setBrush(QColor(26, 115, 232, 25))
            p.drawRect(self.to_scene(pg, run["bbox"]).adjusted(-px, -px, px, px))
        # ghi chú đang chọn
        if self.annot and self.annot_rect is not None and self.annot[0] < len(self.rects):
            sr = self.to_scene(self.annot[0], self.annot_rect)
            p.setPen(QPen(QColor("#1a73e8"), 1.4 * px, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRect(sr)
            if self.annot[2] in MOVABLE and self.annot[2] != "Text" and not self.rot[self.annot[0]][0]:
                h = 5 * px
                p.setPen(QPen(QColor("#1a73e8"), px))
                p.setBrush(Qt.white)
                p.drawRect(QRectF(sr.right() - h, sr.bottom() - h, 2 * h, 2 * h))
        # khung đang kéo
        if self.press is not None and self.cur is not None and self.press_page is not None:
            a, b = self.press, self._clamp_to_page(self.press_page, self.cur)
            col = self.colors["draw"]
            if self.tool in ("rect", "ellipse"):
                p.setPen(QPen(col, self.line_width))
                p.setBrush(Qt.NoBrush)
                (p.drawRect if self.tool == "rect" else p.drawEllipse)(QRectF(a, b).normalized())
            elif self.tool in ("line", "arrow"):
                p.setPen(QPen(col, self.line_width))
                p.drawLine(a, b)
            elif self.tool in ("image", "sign", "erase") or (self.tool == "edittext" and not self.drag_run):
                c = {"erase": QColor("#d93025"), "sign": QColor("#188038")}.get(self.tool, QColor("#1a73e8"))
                p.setPen(QPen(c, 1.3 * px, Qt.DashLine))
                p.setBrush(QColor(c.red(), c.green(), c.blue(), 30))
                p.drawRect(QRectF(a, b).normalized())
        if self.tool == "edittext" and self.drag_run and self.press is not None and self.cur is not None \
                and self.press_page is not None:
            d = self.cur - self.press
            if abs(d.x()) + abs(d.y()) > 3 * px:
                p.setPen(QPen(QColor("#1a73e8"), 1.2 * px, Qt.DashLine))
                p.setBrush(QColor(26, 115, 232, 40))
                p.drawRect(self.to_scene(self.press_page, self.drag_run["bbox"]).translated(d))
        if self.ink:
            p.setPen(QPen(self.colors["draw"], self.line_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            p.drawPolyline(QPolygonF(self.ink))

    def _clamp_to_page(self, i: int, sp: QPointF) -> QPointF:
        r = self.rects[i]
        return QPointF(min(max(sp.x(), r.left()), r.right()), min(max(sp.y(), r.top()), r.bottom()))

    # ------------------------------------------------------------ công cụ
    def set_tool(self, tool: str, payload=None):
        self.tool = tool
        self.payload = payload
        self.press = self.cur = None
        self.ink = []
        self.hover_run = None
        if tool != "hand":
            self.annot = None
        cur = {"hand": Qt.OpenHandCursor, "select": Qt.IBeamCursor, "highlight": Qt.IBeamCursor,
               "underline": Qt.IBeamCursor, "strike": Qt.IBeamCursor, "edittext": Qt.PointingHandCursor,
               "note": Qt.PointingHandCursor}.get(tool, Qt.CrossCursor)
        self.viewport().setCursor(cur)
        hints = {
            "select": "Kéo chuột qua chữ để chọn chữ, hoặc bấm vào một hình ảnh để chọn hình. Ctrl+C để sao chép.",
            "highlight": "Kéo chuột qua chữ để tô sáng. Esc để thôi.",
            "underline": "Kéo chuột qua chữ để gạch chân. Esc để thôi.",
            "strike": "Kéo chuột qua chữ để gạch ngang. Esc để thôi.",
            "edittext": "Bấm vào một dòng chữ để sửa; nắm dòng chữ kéo đi để dời (giữ Ctrl: dời cả đoạn văn); "
                        "kéo khung từ chỗ trống quanh nhiều dòng để sửa cả vùng.",
            "text": "Bấm vào chỗ muốn thêm chữ.",
            "note": "Bấm vào chỗ muốn đặt ghi chú.",
            "image": "Kéo một khung tại chỗ muốn đặt ảnh (hoặc bấm một lần để đặt cỡ mặc định).",
            "sign": "Kéo một khung tại vị trí muốn hiện chữ ký số.",
            "erase": "Kéo một khung quanh vùng cần xoá trắng (nội dung bị xoá hẳn khỏi file).",
            "ink": "Giữ chuột và vẽ tự do. Esc để thôi.",
        }
        self.message.emit(hints.get(tool, ""))
        self.toolChanged.emit(tool)
        self.viewport().update()

    def _color_group(self) -> str:
        if self.tool in MARK_TOOLS:
            return "mark"
        if self.tool in ("text", "edittext"):
            return "text"
        return "draw"

    # ------------------------------------------------------------ chọn chữ
    def _words(self, i: int) -> list:
        if i not in self.words:
            self.words[i] = tools.page_words(self.model.doc[i])
        return self.words[i]

    def _can_auto_ocr(self, i: int) -> bool:
        """Trang không có chữ thật nhưng có hình hoặc nét vẽ (bản scan, file in bằng Microsoft Print to PDF…)."""
        if not AUTO_OCR.get("on") or i in self.ocr_done or self._words(i):
            return False
        page = self.model.doc[i]
        try:
            return bool(page.get_images()) or len(page.read_contents()) > 200
        except Exception:
            return False

    def auto_ocr(self, i: int, quiet: bool = False) -> bool:
        """Nhận dạng chữ trang i ngay (khoảng nửa giây đến vài giây). Trả về True nếu đọc được chữ."""
        if not self._can_auto_ocr(i):
            return i in self.ocr_found
        lang = _auto_ocr_lang()
        self.ocr_done.add(i)
        if not lang:
            return False
        if not quiet:
            self.message.emit(f"Đang tự nhận dạng chữ trang {i + 1}…")
            QApplication.setOverrideCursor(Qt.WaitCursor)
            QApplication.processEvents()
        try:
            ws = tools.ocr_page_words(self.model.doc[i], lang)
        except Exception:
            ws = []
        finally:
            if not quiet:
                QApplication.restoreOverrideCursor()
        if ws:
            self.words[i] = ws
            self.ocr_found.add(i)
        return bool(ws)

    def _nearest_word(self, ws: list, pt: pymupdf.Point) -> int:
        best, bd = 0, 1e18
        for k, w in enumerate(ws):
            dx = max(w[0] - pt.x, 0, pt.x - w[2])
            dy = max(w[1] - pt.y, 0, pt.y - w[3])
            d = dx + 4 * dy
            if d < bd:
                best, bd = k, d
                if d == 0:
                    break
        return best

    def _update_selection(self):
        i = self.press_page
        ws = self._words(i)
        if not ws:
            self.sel_rects, self.sel_text = [], ""
            return
        a = self._nearest_word(ws, self.to_page(i, self.press))
        b = self._nearest_word(ws, self.to_page(i, self.cur))
        a, b = min(a, b), max(a, b)
        lines: dict[tuple, list] = {}
        for w in ws[a:b + 1]:
            lines.setdefault((w[5], w[6]), []).append(w)
        rects, texts = [], []
        for key in lines:
            l = lines[key]
            rects.append(pymupdf.Rect(min(w[0] for w in l), min(w[1] for w in l), max(w[2] for w in l),
                                      max(w[3] for w in l)))
            texts.append(" ".join(w[4] for w in l))
        self.sel_page, self.sel_rects, self.sel_text = i, rects, "\n".join(texts)

    # ------------------------------------------------------------ chọn hình ảnh
    def _images(self, i: int) -> list:
        if i not in self.imgs:
            self.imgs[i] = tools.page_images(self.model.doc[i])
        return self.imgs[i]

    def _select_image(self, i: int, info: dict):
        self.sel_rects, self.sel_text = [], ""
        self.sel_image = (i, info)
        size = f"{info['width']} × {info['height']} px" if info.get("width") else ""
        self.message.emit(f"Đã chọn hình ảnh {size}. Kéo để dời, kéo góc để đổi cỡ (Shift: tự do), kéo nút tròn phía trên "
                          "để xoay (Shift: từng nấc 15°), phím mũi tên để nhích; chuột phải để xoay 90°, lưu, xoá.")
        self.viewport().update()
        self.selectionChanged.emit()

    def _selected_qimage(self):
        i, info = self.sel_image
        pix = tools.image_pixmap(self.model.doc, self.model.doc[i], info)
        fmt = QImage.Format_RGBA8888 if pix.alpha else QImage.Format_RGB888
        return QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()

    def copy_image(self) -> bool:
        if not self.sel_image:
            return False
        QGuiApplication.clipboard().setImage(self._selected_qimage())
        self.message.emit("Đã sao chép hình ảnh. Dán (Ctrl+V) vào Word, Zalo, Paint… để dùng.")
        return True

    def save_image(self) -> bool:
        if not self.sel_image:
            self.message.emit("Chưa chọn hình ảnh nào. Dùng công cụ Chọn rồi bấm vào hình ảnh.")
            return False
        from PySide6.QtWidgets import QFileDialog
        i, info = self.sel_image
        base = os.path.splitext(self.model.title)[0]
        start = os.path.join(os.path.dirname(self.model.path) if self.model.path else "", f"{base}_trang{i + 1}_anh.png")
        path, _ = QFileDialog.getSaveFileName(self, "Lưu hình ảnh", start, "PNG (*.png);;JPG (*.jpg)")
        if not path:
            return False
        if not path.lower().endswith((".png", ".jpg", ".jpeg")):
            path += ".png"
        tools.save_image(self.model.doc, self.model.doc[i], info, path)
        self.message.emit(f"Đã lưu hình ảnh: {path}")
        return True

    def delete_image(self) -> bool:
        if not self.sel_image:
            return False
        i, info = self.sel_image
        self.sel_image = None
        with self.model.edit(i):
            tools.delete_image(self.model.doc[i], info)
        self.message.emit("Đã xoá hình ảnh khỏi trang (Ctrl+Z để lấy lại).")
        return True

    # ------------------------------------------------------------ dời / co giãn / xoay hình ảnh
    def _spt(self, i: int, pt) -> QPointF:
        """Điểm trên trang -> toạ độ cảnh."""
        pt = pymupdf.Point(pt)
        return self.to_scene(i, pymupdf.Rect(pt, pt)).topLeft()

    def _img_hit(self, sp: QPointF):
        """Chỗ bấm so với ảnh đang chọn: 'rotate' | ('scale', số góc) | 'move' | None."""
        if not self.sel_image:
            return None
        i, info = self.sel_image
        if i >= len(self.rects):
            return None
        h = 7 / max(0.01, self.transform().m11())
        r = pymupdf.Rect(info["bbox"])
        if not info.get("annot"):
            rot = self._img_rot_handle(i, r)
            if abs(sp.x() - rot.x()) <= h * 1.3 and abs(sp.y() - rot.y()) <= h * 1.3:
                return "rotate"
        for k, c in enumerate((r.tl, r.tr, r.bl, r.br)):
            q = self._spt(i, c)
            if abs(sp.x() - q.x()) <= h and abs(sp.y() - q.y()) <= h:
                return ("scale", k)
        if self.to_scene(i, r).contains(sp):
            return "move"
        return None

    def _img_rot_handle(self, i: int, r) -> QPointF:
        top = self._spt(i, pymupdf.Point((r.x0 + r.x1) / 2, r.y0))
        return QPointF(top.x(), top.y() - 26 / max(0.01, self.transform().m11()))

    def _img_matrix(self, pt, shift: bool):
        d = self.img_drag
        mode, start = d["mode"], d["start"]
        T = lambda x, y: pymupdf.Matrix(1, 0, 0, 1, x, y)
        if mode == "move":
            return T(pt.x - start.x, pt.y - start.y)
        if mode == "rotate":
            c = d["center"]
            a0 = math.degrees(math.atan2(start.y - c.y, start.x - c.x))
            a1 = math.degrees(math.atan2(pt.y - c.y, pt.x - c.x))
            ang = a1 - a0
            if shift:
                ang = round(ang / 15) * 15
            d["angle"] = ang
            return T(-c.x, -c.y) * pymupdf.Matrix(ang) * T(c.x, c.y)
        anchor, corner = d["anchor"], d["corner"]
        v0x, v0y = corner.x - anchor.x, corner.y - anchor.y
        sx = (pt.x - anchor.x) / v0x if abs(v0x) > 0.01 else 1
        sy = (pt.y - anchor.y) / v0y if abs(v0y) > 0.01 else 1
        if shift:          # giữ Shift: co giãn tự do từng chiều
            sx, sy = max(0.05, sx), max(0.05, sy)
        else:              # mặc định giữ đúng tỉ lệ ảnh
            sx = sy = max(0.05, (sx + sy) / 2)
        return T(-anchor.x, -anchor.y) * pymupdf.Matrix(sx, sy) * T(anchor.x, anchor.y)

    def _img_drag_start(self, i: int, sp: QPointF, hit) -> None:
        info = self.sel_image[1]
        r = pymupdf.Rect(info["bbox"])
        corners = (r.tl, r.tr, r.bl, r.br)
        d = {"i": i, "info": info, "start": self.to_page(i, sp, clamp=False), "A": pymupdf.Matrix(1, 0, 0, 1, 0, 0),
             "center": (r.tl + r.br) / 2}
        if isinstance(hit, tuple):
            d["mode"], d["corner"], d["anchor"] = "scale", corners[hit[1]], corners[3 - hit[1]]
        else:
            d["mode"] = hit
        try:            # ảnh đúng như đang hiện trên trang (vẽ riêng vùng của ảnh), để kéo tới đâu thấy ảnh tới đó
            z = max(0.5, min(3.0, self.to_scene(i, r).width() * self.transform().m11() / max(1.0, r.width)))
            pm = self.model.doc[i].get_pixmap(matrix=pymupdf.Matrix(z, z), clip=r, alpha=False)
            img = QImage(pm.samples, pm.width, pm.height, pm.stride, QImage.Format_RGB888).copy()
            from PySide6.QtGui import QPixmap
            d["pix"] = QPixmap.fromImage(img)
        except Exception:
            d["pix"] = None
        self.img_drag = d

    def _commit_image(self, i: int, info: dict, A) -> None:
        r = pymupdf.Rect(info["bbox"])
        new = (r.quad * A).rect
        with self.model.edit(i):
            page = self.model.doc[i]
            if info.get("annot"):          # ảnh chèn dạng con dấu / chữ ký: đổi khung của ghi chú
                for an in list(page.annots() or []):
                    if an.type[1] == "Stamp" and (pymupdf.Rect(an.rect) & r).get_area() > 0.5 * r.get_area():
                        an.set_rect(new)
                        an.update()
                        break
                else:
                    raise tools.ImageEditError("Hình này thuộc khung chữ ký số hoặc ô biểu mẫu nên không sửa riêng được.")
            else:
                tools.transform_image(page, info, A)
        # chọn lại đúng ảnh đó ở chỗ mới
        self.imgs.pop(i, None)
        best = None
        for d in self._images(i):
            if d.get("xref") == info.get("xref") or info.get("annot"):
                dist = abs(d["bbox"].x0 - new.x0) + abs(d["bbox"].y0 - new.y0) + abs(d["bbox"].x1 - new.x1) \
                    + abs(d["bbox"].y1 - new.y1)
                if best is None or dist < best[0]:
                    best = (dist, d)
        if best:
            self.sel_image = (i, best[1])
            self.selectionChanged.emit()
        else:
            self.sel_image = None

    def rotate_image(self, deg: float) -> None:
        """Xoay ảnh đang chọn quanh tâm của nó (độ, chiều kim đồng hồ)."""
        if not self.sel_image:
            return
        i, info = self.sel_image
        if info.get("annot"):
            self.message.emit("Ảnh chèn dạng con dấu / chữ ký chỉ dời và đổi cỡ được, chưa xoay được.")
            return
        r = pymupdf.Rect(info["bbox"])
        c = (r.tl + r.br) / 2
        A = pymupdf.Matrix(1, 0, 0, 1, -c.x, -c.y) * pymupdf.Matrix(deg) * pymupdf.Matrix(1, 0, 0, 1, c.x, c.y)
        self._commit_image(i, info, A)
        self.message.emit(f"Đã xoay hình ảnh {abs(deg):g}° (Ctrl+Z để hoàn tác).")
        self.viewport().update()

    def nudge_image(self, dx: float, dy: float) -> None:
        if self.sel_image:
            i, info = self.sel_image
            self._commit_image(i, info, pymupdf.Matrix(1, 0, 0, 1, dx, dy))
            self.viewport().update()

    def clear_selection(self):
        self.sel_image = None
        self.sel_rects, self.sel_text, self.sel_page = [], "", None
        self.viewport().update()
        self.selectionChanged.emit()

    def copy_selection(self) -> bool:
        if self.sel_image:
            return self.copy_image()
        if self.sel_text:
            QGuiApplication.clipboard().setText(self.sel_text)
            self.message.emit("Đã sao chép chữ đang chọn.")
            return True
        return False

    def mark_selection(self, kind: str):
        if not self.sel_rects or self.sel_page is None:
            return
        i, rects = self.sel_page, list(self.sel_rects)
        col = qcolor_to_rgb(self.colors["mark"] if kind == "highlight" else self.colors["draw"])
        with self.model.edit(i):
            page = self.model.doc[i]
            fn = {"highlight": page.add_highlight_annot, "underline": page.add_underline_annot,
                  "strike": page.add_strikeout_annot}[kind]
            a = fn(quads=[r.quad for r in rects])
            a.set_colors(stroke=col)
            a.update()
        self.clear_selection()

    # ------------------------------------------------------------ ghi chú
    def _annot_at(self, i: int, pt: pymupdf.Point):
        found = None
        try:
            for a in self.model.doc[i].annots():
                if pt in a.rect + (-2, -2, 2, 2):
                    found = (i, a.xref, a.type[1], pymupdf.Rect(a.rect))
        except Exception:
            pass
        return found

    def _load_annot(self):
        if not self.annot:
            return None, None
        page = self.model.doc[self.annot[0]]
        try:
            return page, page.load_annot(self.annot[1])
        except Exception:
            return page, None

    def _hover_note(self, e, sp):
        """Rê chuột vào ghi chú (hoặc phần tô sáng/hình vẽ có lời ghi) thì hiện nội dung ngay cạnh con trỏ."""
        import html as _html
        i = self.page_at(sp, clamp=False)
        hit = None
        if i is not None:
            if i not in self.notes:
                self.notes[i] = tools.page_notes(self.model.doc[i])
            if self.notes[i]:
                pt = self.to_page(i, sp)
                for rect, kind, text, who, when in self.notes[i]:
                    if pt in rect + (-2, -2, 2, 2):
                        hit = (i, rect.x0, rect.y0, kind, text, who, when)
        if hit is None:
            if self._note_tip is not None:
                self._note_tip = None
                QToolTip.hideText()
            return
        if hit != self._note_tip:
            self._note_tip = hit
            head = "Ghi chú" + (f" · {_html.escape(hit[5])}" if hit[5] else "") + (f" · {hit[6][:16]}" if hit[6] else "")
            body = _html.escape(hit[4]).replace("\n", "<br>")
            QToolTip.showText(e.globalPosition().toPoint(),
                              f"<div style='max-width:360px'><div style='color:#80868b;font-size:11px'>{head}</div>"
                              f"<div style='margin-top:3px'>{body}</div></div>", self.viewport())

    def delete_selected_annot(self) -> bool:
        if not self.annot:
            return False
        i, xref = self.annot[0], self.annot[1]
        self.annot = None
        with self.model.edit(i):
            page = self.model.doc[i]
            for a in page.annots():
                if a.xref == xref:
                    page.delete_annot(a)
                    break
        return True

    def edit_selected_annot(self):
        if not self.annot or self.annot[2] != "Text":
            return
        i, xref = self.annot[0], self.annot[1]
        page = self.model.doc[i]
        a = page.load_annot(xref)
        text, ok = QInputDialog.getMultiLineText(self, "Sửa ghi chú", "Nội dung:", a.info.get("content", ""))
        if ok:
            with self.model.edit(i):
                page = self.model.doc[i]
                a = page.load_annot(xref)
                a.set_info(content=text)
                a.update()

    # ------------------------------------------------------------ biểu mẫu, liên kết
    def _click_widget(self, i: int, pt) -> bool:
        page = self.model.doc[i]
        try:
            widgets = list(page.widgets())
        except Exception:
            return False
        for w in widgets:
            if pt not in w.rect:
                continue
            t = w.field_type
            if t == pymupdf.PDF_WIDGET_TYPE_SIGNATURE:
                self.message.emit("Đây là ô chữ ký số. Dùng menu Ký & Bảo mật để ký hoặc kiểm tra chữ ký.")
                return True
            if w.field_flags & 1:  # chỉ đọc
                return True
            name = w.field_label or w.field_name or "Ô nhập"
            xref = w.xref
            new = None
            if t == pymupdf.PDF_WIDGET_TYPE_CHECKBOX:
                new = not bool(w.field_value and str(w.field_value) not in ("Off", "False"))
            elif t == pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON:
                new = True
            elif t in (pymupdf.PDF_WIDGET_TYPE_COMBOBOX, pymupdf.PDF_WIDGET_TYPE_LISTBOX):
                opts = [o[1] if isinstance(o, (list, tuple)) else o for o in (w.choice_values or [])]
                cur = opts.index(w.field_value) if w.field_value in opts else 0
                val, ok = QInputDialog.getItem(self, "Điền biểu mẫu", name, opts, cur,
                                               t == pymupdf.PDF_WIDGET_TYPE_COMBOBOX)
                if not ok:
                    return True
                new = val
            elif t == pymupdf.PDF_WIDGET_TYPE_TEXT:
                multi = bool(w.field_flags & pymupdf.PDF_TX_FIELD_IS_MULTILINE)
                if multi:
                    val, ok = QInputDialog.getMultiLineText(self, "Điền biểu mẫu", name, w.field_value or "")
                else:
                    val, ok = QInputDialog.getText(self, "Điền biểu mẫu", name, text=w.field_value or "")
                if not ok:
                    return True
                new = val
            else:
                return True
            with self.model.edit(i):
                for ww in self.model.doc[i].widgets():
                    if ww.xref == xref:
                        ww.field_value = new
                        ww.update()
                        break
            return True
        return False

    def _click_link(self, i: int, pt) -> bool:
        try:
            links = self.model.doc[i].get_links()
        except Exception:
            return False
        for l in links:
            if pt in pymupdf.Rect(l["from"]):
                if l["kind"] == pymupdf.LINK_GOTO and l.get("page", -1) >= 0:
                    to = l.get("to")
                    self.goto_page(l["page"], to.y if to else 0)
                    return True
                if l["kind"] == pymupdf.LINK_URI and l.get("uri"):
                    uri = l["uri"]
                    if QMessageBox.question(self, "Mở liên kết", f"Mở liên kết này trong trình duyệt?\n\n{uri}") \
                            == QMessageBox.Yes:
                        QDesktopServices.openUrl(QUrl(uri))
                    return True
        return False

    # ------------------------------------------------------------ chuột
    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return super().mousePressEvent(e)
        sp = self.mapToScene(e.position().toPoint())
        i = self.page_at(sp, clamp=False)
        self.cur = sp
        if self.tool == "hand":
            if i is not None:
                pt = self.to_page(i, sp)
                if self.annot and self.annot[0] == i and self.annot[2] in MOVABLE:
                    r = self.annot_rect
                    h = 7 / self.transform().m11()
                    if self.annot[2] != "Text" and not self.rot[i][0] and abs(pt.x - r.x1) <= h \
                            and abs(pt.y - r.y1) <= h:
                        self.annot_mode, self.annot_off = "resize", pt
                        return
                hit = self._annot_at(i, pt)
                if hit:
                    self.annot = hit[:3]
                    self.annot_rect = hit[3]
                    if hit[2] in MOVABLE:
                        self.annot_mode, self.annot_off = "move", pt - hit[3].tl
                    self.viewport().update()
                    return
            if self.annot:
                self.annot = None
                self.viewport().update()
            self.pan = (e.position(), self.horizontalScrollBar().value(), self.verticalScrollBar().value(), i, sp)
            self.viewport().setCursor(Qt.ClosedHandCursor)
            return
        if self.tool == "select" and self.sel_image and not self.rot[self.sel_image[0]][0]:
            hit = self._img_hit(sp)
            if hit:                      # nắm vào ảnh đang chọn: dời / co giãn (góc) / xoay (nút tròn phía trên)
                self._img_drag_start(self.sel_image[0], sp, hit)
                return
        if i is None:
            return
        self.press, self.press_page = sp, i
        if self.tool == "ink":
            self.ink = [sp]
        elif self.tool == "edittext":
            # bấm vào một dòng chữ rồi kéo = dời dòng đó (giữ Ctrl: dời cả đoạn văn);
            # bấm ở chỗ trống rồi kéo = quét khung quanh nhiều dòng để sửa cả vùng
            page = self.model.doc[i]
            run = tools.text_run_at(page, self.to_page(i, sp))
            self.drag_run = None
            if run is not None:
                self.drag_run = dict(run)
                self.drag_run["_group"] = tools.paragraph_runs(page, run) if e.modifiers() & Qt.ControlModifier else [run]
                box = pymupdf.Rect(run["bbox"])
                for r in self.drag_run["_group"]:
                    box |= r["bbox"]
                self.drag_run["bbox"] = box
        elif self.tool == "select" or self.tool in MARK_TOOLS:
            self.sel_rects, self.sel_text = [], ""
            self.sel_image = None
            if not self._words(i) and self.auto_ocr(i):
                self.message.emit("Trang này không có chữ thật (chữ là ảnh/nét vẽ): app đã tự nhận dạng để chọn, sao chép, "
                                  "tìm kiếm. Muốn lưu lớp chữ vào file thì dùng Chuyển đổi → Nhận dạng chữ (OCR).")
            elif not self._words(i) and not (self.tool == "select" and self._images(i)):
                self.message.emit("Trang này không có chữ thật: chữ chỉ là ảnh hoặc nét vẽ (bản scan, hoặc file in ra PDF bằng "
                                  "“Microsoft Print to PDF”). Chạy Chuyển đổi → Nhận dạng chữ (OCR) để chọn và sao chép được.")
        self.viewport().update()

    def mouseMoveEvent(self, e):
        self.last_scroll = time.perf_counter()
        sp = self.mapToScene(e.position().toPoint())
        self.cur = sp
        if self.img_drag is not None:
            d = self.img_drag
            d["A"] = self._img_matrix(self.to_page(d["i"], sp, clamp=False), bool(e.modifiers() & Qt.ShiftModifier))
            if d["mode"] == "rotate":
                self.message.emit(f"Xoay {d.get('angle', 0):.0f}° (giữ Shift để xoay từng nấc 15°)")
            self.viewport().update()
            return
        if self.tool == "select" and self.press is None and self.sel_image:
            hit = self._img_hit(sp)
            cur = Qt.IBeamCursor
            if hit == "move":
                cur = Qt.SizeAllCursor
            elif hit == "rotate":
                cur = Qt.PointingHandCursor
            elif isinstance(hit, tuple):
                cur = Qt.SizeFDiagCursor if hit[1] in (0, 3) else Qt.SizeBDiagCursor
            self.viewport().setCursor(cur)
        if self.pan:
            d = e.position() - self.pan[0]
            self.horizontalScrollBar().setValue(int(self.pan[1] - d.x()))
            self.verticalScrollBar().setValue(int(self.pan[2] - d.y()))
            return
        if self.annot_mode and self.annot:
            i = self.annot[0]
            pt = self.to_page(i, sp)
            r = pymupdf.Rect(self.annot_rect)
            if self.annot_mode == "move":
                tl = pt - self.annot_off
                ub = self.rot[i][3]
                tl = pymupdf.Point(min(max(tl.x, ub.x0), ub.x1 - r.width), min(max(tl.y, ub.y0), ub.y1 - r.height))
                self.annot_rect = pymupdf.Rect(tl.x, tl.y, tl.x + r.width, tl.y + r.height)
            else:
                self.annot_rect = pymupdf.Rect(r.x0, r.y0, max(pt.x, r.x0 + 8), max(pt.y, r.y0 + 8))
            self.annot_moved = True
            self.viewport().update()
            return
        if self.press is None:
            self._hover_note(e, sp)
        if self.tool == "edittext" and self.press is None:
            i = self.page_at(sp, clamp=False)
            run = None
            if i is not None:
                if i not in self.dicts:
                    self.dicts[i] = tools.text_dict(self.model.doc[i])
                run = tools.text_run_at(self.model.doc[i], self.to_page(i, sp), d=self.dicts[i])
            new = (i, run) if run else None
            if (new is None) != (self.hover_run is None) or (new and self.hover_run and
                                                             new[1]["bbox"] != self.hover_run[1]["bbox"]):
                self.hover_run = new
                self.viewport().update()
            return
        if self.press is None:
            return
        if self.tool == "ink":
            self.ink.append(self._clamp_to_page(self.press_page, sp))
        elif self.tool == "select" or self.tool in MARK_TOOLS:
            self._update_selection()
        self.viewport().update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton:
            return super().mouseReleaseEvent(e)
        sp = self.mapToScene(e.position().toPoint())
        try:
            self._release(e, sp)
        except Exception as ex:
            QMessageBox.warning(self, "PDF Editor Lite", f"Không thực hiện được thao tác:\n{ex}")
        finally:
            self.press = None
            self.ink = []
            self.pan = None
            self.annot_mode = None
            self.viewport().update()

    def _release(self, e, sp: QPointF):
        if self.img_drag is not None:
            d, self.img_drag = self.img_drag, None
            A = d["A"]
            moved = abs(A.a - 1) + abs(A.b) + abs(A.c) + abs(A.d - 1) > 1e-3 or abs(A.e) + abs(A.f) > 0.5
            if moved:
                try:
                    self._commit_image(d["i"], d["info"], A)
                    what = {"move": "Đã dời", "scale": "Đã đổi cỡ", "rotate": "Đã xoay"}[d["mode"]]
                    self.message.emit(f"{what} hình ảnh (Ctrl+Z để hoàn tác).")
                except tools.ImageEditError as ex:
                    self.message.emit(str(ex))
                    QMessageBox.information(self, "PDF Editor Lite", str(ex))
            return
        if self.pan:
            start, _h, _v, i, sp0 = self.pan
            self.pan = None
            self.viewport().setCursor(Qt.OpenHandCursor)
            if (e.position() - start).manhattanLength() < 4 and i is not None:
                pt = self.to_page(i, sp0)
                if not self._click_widget(i, pt):
                    self._click_link(i, pt)
            return
        if self.annot_mode and self.annot:
            if getattr(self, "annot_moved", False):
                self.annot_moved = False
                i, xref = self.annot[0], self.annot[1]
                rect = pymupdf.Rect(self.annot_rect)
                with self.model.edit(i):
                    page = self.model.doc[i]
                    a = page.load_annot(xref)
                    a.set_rect(rect)
                    a.update()
                page = self.model.doc[i]
                self.annot_rect = pymupdf.Rect(page.load_annot(xref).rect)
            return
        if self.press is None or self.press_page is None:
            return
        i = self.press_page
        a, b = self.to_page(i, self.press), self.to_page(i, sp)
        rect = pymupdf.Rect(a, b)
        rect.normalize()
        small = rect.width < 4 and rect.height < 4
        tool = self.tool
        col = qcolor_to_rgb(self.colors["draw"])
        if tool == "select":
            if small:  # bấm một lần (không kéo): chọn hình ảnh tại đó nếu có
                self.sel_rects, self.sel_text = [], ""
                hit = tools.image_at(self._images(i), a)
                if hit:
                    self._select_image(i, hit)
                    return
            self.selectionChanged.emit()
            if self.sel_text:
                self.message.emit(f"Đã chọn {len(self.sel_text)} ký tự. Ctrl+C để sao chép, chuột phải để tô sáng.")
        elif tool in MARK_TOOLS:
            if self.sel_rects:
                self.mark_selection(tool)
        elif tool == "ink":
            pts = [tuple(self.to_page(i, q)) for q in self.ink]
            if len(pts) > 1:
                with self.model.edit(i):
                    page = self.model.doc[i]
                    an = page.add_ink_annot([pts])
                    an.set_colors(stroke=col)
                    an.set_border(width=self.line_width)
                    an.update()
        elif tool in ("rect", "ellipse") and not small:
            with self.model.edit(i):
                page = self.model.doc[i]
                an = page.add_rect_annot(rect) if tool == "rect" else page.add_circle_annot(rect)
                an.set_colors(stroke=col)
                an.set_border(width=self.line_width)
                an.update()
        elif tool in ("line", "arrow") and not small:
            with self.model.edit(i):
                page = self.model.doc[i]
                an = page.add_line_annot(a, b)
                if tool == "arrow":
                    an.set_line_ends(pymupdf.PDF_ANNOT_LE_NONE, pymupdf.PDF_ANNOT_LE_CLOSED_ARROW)
                an.set_colors(stroke=col, fill=col)
                an.set_border(width=self.line_width)
                an.update()
        elif tool == "erase" and not small:
            with self.model.edit(i):
                page = self.model.doc[i]
                page.add_redact_annot(rect, fill=(1, 1, 1), cross_out=False)
                page.apply_redactions()
        elif tool == "note":
            text, ok = QInputDialog.getMultiLineText(self, "Ghi chú", "Nội dung ghi chú:")
            if ok and text.strip():
                with self.model.edit(i):
                    page = self.model.doc[i]
                    an = page.add_text_annot(a, text, icon="Comment")
                    an.set_colors(stroke=(1, 0.82, 0))
                    an.set_info(content=text, subject=tools.NOTE_MARK, title=_user_name())
                    an.update()
            self.set_tool("hand")
        elif tool == "text":
            from .dialogs import TextDialog
            dlg = TextDialog(self, "Thêm chữ", "", self.font_size, self.colors["text"], family=self.font_family)
            if dlg.exec() and dlg.text().strip():
                self.font_size, self.colors["text"], self.font_family = dlg.size(), dlg.color(), dlg.family()
                top_left = self.to_display(i, a if small else rect.tl)
                if not small and self.rot[i][0]:
                    dr = rect * self.rot[i][1]
                    dr.normalize()
                    top_left = dr.tl
                with self.model.edit(i):
                    tools.insert_text_lines(self.model.doc[i], top_left, dlg.text(), dlg.size(),
                                            qcolor_to_rgb(dlg.color()), dlg.family())
                    self.model.fonts_added = True
                self.message.emit("Đã thêm chữ. Muốn sửa hoặc dời chỗ: chọn công cụ Sửa chữ gốc rồi bấm/kéo dòng chữ.")
            self.set_tool("hand")
        elif tool == "image":
            path = self.payload
            if self.rot[i][0]:  # xoay ảnh ngược lại để ảnh đứng thẳng trên trang đang xoay
                img = QImage(path).transformed(QTransform().rotate(-self.rot[i][0]), Qt.SmoothTransformation)
                fd, tmp = tempfile.mkstemp(suffix=".png")
                os.close(fd)
                img.save(tmp)
                pix = pymupdf.Pixmap(tmp)
                os.unlink(tmp)
            else:
                pix = pymupdf.Pixmap(path)
            if small:
                w = min(160.0, self.rects[i].width() * 0.4)
                h = w * pix.height / max(1, pix.width)
                rect = pymupdf.Rect(a.x - w / 2, a.y - h / 2, a.x + w / 2, a.y + h / 2)
            else:  # giữ đúng tỉ lệ ảnh trong khung đã kéo
                k = min(rect.width / pix.width, rect.height / pix.height)
                w, h = pix.width * k, pix.height * k
                c = (rect.tl + rect.br) / 2
                rect = pymupdf.Rect(c.x - w / 2, c.y - h / 2, c.x + w / 2, c.y + h / 2)
            with self.model.edit(i):
                page = self.model.doc[i]
                an = page.add_stamp_annot(rect, stamp=pix)
                an.set_info(subject="lp|image")
            self.set_tool("hand")
            an = self._annot_at(i, (rect.tl + rect.br) / 2)
            if an:
                self.annot, self.annot_rect = an[:3], an[3]
            self.message.emit("Đã đặt ảnh. Kéo để di chuyển, kéo góc dưới phải để đổi cỡ, Delete để xoá.")
        elif tool == "sign":
            if rect.width < 30 or rect.height < 15:
                self.message.emit("Khung chữ ký quá nhỏ, hãy kéo khung lớn hơn.")
                return
            self.set_tool("hand")
            self.signRequested.emit(i, rect)
        elif tool == "edittext":
            if not small and self.drag_run:
                group = self.drag_run["_group"]
                d = b - a
                with self.model.edit(i):
                    used = tools.move_text_runs(self.model.doc[i], group, d.x, d.y)
                    self.model.fonts_added = True
                what = "dòng chữ" if len(group) == 1 else f"đoạn văn {len(group)} dòng"
                self.message.emit(f"Đã dời {what}" + (f" (phông thay thế: {used})." if used else ".")
                                  + " Ctrl+Z để hoàn tác.")
            elif small and self.drag_run is not None:
                self._edit_text_at(i, a)
            elif not small:
                self._edit_text_region(i, rect)
            else:
                self._edit_text_at(i, a)
            self.drag_run = None

    def _edit_text_region(self, i: int, rect):
        """Quét một khung: sửa mọi dòng chữ gốc trong khung cùng lúc (mỗi dòng trong hộp ứng với một dòng chữ)."""
        from .dialogs import RichTextDialog
        runs = tools.text_runs_in(self.model.doc[i], rect)
        if not runs:
            self.message.emit("Không có chữ gốc trong khung vừa quét (nếu là bản scan thì dùng Xoá vùng + Thêm chữ).")
            return
        if len(runs) == 1:
            return self._edit_text_at(i, (runs[0]["bbox"].tl + runs[0]["bbox"].br) / 2)
        if len(runs) > 400:
            self.message.emit("Khung vừa quét có quá nhiều dòng chữ. Hãy quét vùng nhỏ hơn.")
            return
        note = (f"{len(runs)} dòng chữ trong vùng đã quét, xếp từ trên xuống, trái sang phải (mỗi ô của bảng là một dòng). "
                "Mỗi dòng ở đây thay cho đúng một dòng trên trang; xoá trống một dòng là xoá dòng đó; dòng không sửa thì giữ nguyên. "
                "Bôi chọn chữ rồi bấm B / I / Màu chữ để định dạng riêng phần đó. Dòng dài quá bề rộng gốc sẽ tự xuống dòng.")
        dlg = RichTextDialog(self, "Sửa chữ gốc trong vùng đã quét", [list(r["segs"]) for r in runs],
                             round(runs[0]["size"], 2), note=note)
        if not dlg.exec():
            return
        lines = dlg.lines()
        while lines and not tools.segs_text(lines[-1]).strip() and len(lines) > len(runs):
            lines.pop()
        try:
            with self.model.edit(i):
                used = tools.replace_text_runs(self.model.doc[i], runs, lines, dlg.size())
                self.model.fonts_added = True
        except tools.NoRoom as e:
            QMessageBox.information(self, "Sửa chữ gốc", "Có dòng dài hơn bề rộng gốc nên cần xuống dòng, nhưng:\n\n" + str(e)
                                    + "\n\nChưa có gì bị thay đổi.")
            return
        self.hover_run = None
        self.message.emit("Đã sửa các dòng chữ trong vùng" + (f" (phông thay thế: {used})." if used else "."))

    def _edit_text_at(self, i: int, pt):
        from .dialogs import RichTextDialog
        run = tools.text_run_at(self.model.doc[i], pt)
        if not run:
            self.message.emit("Không có chữ gốc tại vị trí này (nếu là bản scan thì dùng Xoá vùng + Thêm chữ).")
            return
        dlg = RichTextDialog(self, "Sửa chữ gốc", [list(run["segs"])], round(run["size"], 2), single_line=True,
                             note=f"Phông gốc: {run['font'].split('+')[-1]}. Bôi chọn chữ rồi bấm B / I / Màu chữ để định dạng "
                                  "riêng phần đó. Chữ dài hơn bề rộng của dòng sẽ tự xuống dòng. Xoá hết chữ rồi OK để xoá dòng này.")
        if not dlg.exec():
            return
        segs = dlg.lines()[0]
        if dlg.size() is None and tools._norm_segs(segs) == tools._norm_segs(run["segs"]):
            self.message.emit("Không có gì thay đổi.")
            return
        n = 1
        try:
            with self.model.edit(i):
                page = self.model.doc[i]
                used, n = tools.replace_text_run_wrapped(page, run, segs, dlg.size())
                self.model.fonts_added = True
        except tools.NoRoom as e:                # không xuống dòng được: trang đã được trả về như cũ
            QMessageBox.information(self, "Sửa chữ gốc", "Chữ mới dài hơn bề rộng của dòng nên cần xuống dòng, nhưng:\n\n" + str(e)
                                    + "\n\nChưa có gì bị thay đổi.")
            return
        self.hover_run = None
        if used:
            self.message.emit(f"Đã sửa chữ (phông thay thế: {used})."
                              + (f" Chữ dài hơn bề rộng dòng nên đã xuống thành {n} dòng." if n > 1 else ""))

    def mouseDoubleClickEvent(self, e):
        if self.tool == "hand" and e.button() == Qt.LeftButton:
            sp = self.mapToScene(e.position().toPoint())
            i = self.page_at(sp, clamp=False)
            if i is not None:
                hit = self._annot_at(i, self.to_page(i, sp))
                if hit and hit[2] == "Text":
                    self.annot, self.annot_rect = hit[:3], hit[3]
                    self.annot_mode = None
                    self.edit_selected_annot()
                    return
        super().mouseDoubleClickEvent(e)

    def contextMenuEvent(self, e):
        sp = self.mapToScene(e.pos())
        i = self.page_at(sp, clamp=False)
        m = QMenu(self)
        if self.sel_text:
            m.addAction(icon_for("Sao chép"), "Sao chép", self.copy_selection)
            m.addAction(icon_for("Tô sáng"), "Tô sáng", lambda: self.mark_selection("highlight"))
            m.addAction(icon_for("Gạch chân"), "Gạch chân", lambda: self.mark_selection("underline"))
            m.addAction(icon_for("Gạch ngang"), "Gạch ngang", lambda: self.mark_selection("strike"))
            m.addSeparator()
        if i is not None:
            pt0 = self.to_page(i, sp)
            img = tools.image_at(self._images(i), pt0)
            if img and not self.sel_text and not self._annot_at(i, pt0):
                self._select_image(i, img)
                m.addAction(icon_for("Sao chép hình ảnh"), "Sao chép hình ảnh", lambda: self._safe(self.copy_image))
                m.addAction(icon_for("Lưu hình ảnh thành file…"), "Lưu hình ảnh thành file…", lambda: self._safe(self.save_image))
                m.addAction(icon_for("Xoá hình ảnh khỏi trang"), "Xoá hình ảnh khỏi trang", lambda: self._safe(self.delete_image))
                if not self.sel_image[1].get("annot"):
                    m.addSeparator()
                    m.addAction(icon("rotr"), "Xoay phải 90°", lambda: self._safe(self.rotate_image, 90))
                    m.addAction(icon("rotl"), "Xoay trái 90°", lambda: self._safe(self.rotate_image, -90))
                    m.addAction(icon("rotr"), "Xoay 180°", lambda: self._safe(self.rotate_image, 180))
                m.addSeparator()
        if i is not None:
            pt = self.to_page(i, sp)
            hit = self._annot_at(i, pt)
            if hit:
                self.annot, self.annot_rect = hit[:3], hit[3]
                self.viewport().update()
                if hit[2] == "Text":
                    m.addAction(icon_for("Sửa nội dung…"), "Sửa nội dung…", self.edit_selected_annot)
                m.addAction(icon_for("Xoá ghi chú/ảnh này"), "Xoá ghi chú/ảnh này", self.delete_selected_annot)
                m.addSeparator()
            m.addAction(icon_for("Sửa chữ gốc tại đây…"), "Sửa chữ gốc tại đây…", lambda: self._safe(self._edit_text_at, i, pt))
        m.addAction(icon_for("Công cụ bàn tay"), "Công cụ bàn tay", lambda: self.set_tool("hand"))
        m.addAction(icon_for("Công cụ chọn chữ / hình ảnh"), "Công cụ chọn chữ / hình ảnh", lambda: self.set_tool("select"))
        m.exec(e.globalPos())

    def _safe(self, fn, *a):
        try:
            fn(*a)
        except Exception as ex:
            QMessageBox.warning(self, "PDF Editor Lite", f"Không thực hiện được thao tác:\n{ex}")

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key_Escape:
            self.clear_selection()
            self.annot = None
            if self.tool != "hand":
                self.set_tool("hand")
            return
        if self.sel_image and not self.annot and k in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down) \
                and self.tool == "select":           # phím mũi tên: nhích ảnh đang chọn 1 điểm (Shift: 10 điểm)
            st = 10.0 if e.modifiers() & Qt.ShiftModifier else 1.0
            dx = {Qt.Key_Left: -st, Qt.Key_Right: st}.get(k, 0.0)
            dy = {Qt.Key_Up: -st, Qt.Key_Down: st}.get(k, 0.0)
            self._safe(self.nudge_image, dx, dy)
            return
        if k in (Qt.Key_Delete, Qt.Key_Backspace) and self.sel_image and not self.annot:
            self._safe(self.delete_image)
            return
        if k in (Qt.Key_Delete, Qt.Key_Backspace) and self.annot:
            self._safe(self.delete_selected_annot)
            return
        if k in (Qt.Key_PageDown, Qt.Key_Space):
            sb = self.verticalScrollBar()
            sb.setValue(sb.value() + int(self.viewport().height() * 0.9))
            return
        if k == Qt.Key_PageUp:
            sb = self.verticalScrollBar()
            sb.setValue(sb.value() - int(self.viewport().height() * 0.9))
            return
        if k == Qt.Key_Home and e.modifiers() & Qt.ControlModifier:
            return self.goto_page(0)
        if k == Qt.Key_End and e.modifiers() & Qt.ControlModifier:
            return self.goto_page(len(self.rects) - 1)
        super().keyPressEvent(e)

    # ------------------------------------------------------------ tìm kiếm
    def _reset_search(self):
        self._search_timer.stop()
        self.hits, self.hit_pages, self.hit_idx, self.query = [], [], -1, ""
        self._scan, self._scan_pos = [], 0

    def _scanning(self) -> bool:
        return self._scan_pos < len(self._scan)

    def _scan_some(self, budget: float, first_only: bool = False):
        """Dò tiếp các trang chưa tìm, trong khoảng thời gian cho phép. Kết quả luôn xếp theo thứ tự trang."""
        end = time.perf_counter() + budget
        doc = self.model.doc
        while self._scan_pos < len(self._scan):
            i = self._scan[self._scan_pos]
            self._scan_pos += 1
            try:
                if i in self.ocr_found:
                    rs = tools.search_words(self.words.get(i, []), self.query)
                else:
                    rs = tools.search_page(doc[i], self.query)
                    if not rs and self.model.page_count <= AUTO_OCR.get("max_search_pages", 60) \
                            and self._can_auto_ocr(i) and self.auto_ocr(i, quiet=True):
                        rs = tools.search_words(self.words.get(i, []), self.query)
            except Exception:
                rs = []
            if rs:
                k = bisect.bisect_left(self.hit_pages, i)
                self.hits[k:k] = [(i, r) for r in rs]
                self.hit_pages[k:k] = [i] * len(rs)
                if self.hit_idx >= k:
                    self.hit_idx += len(rs)
                if len(self.hits) > 5000:
                    self._scan_pos = len(self._scan)
                    break
                if first_only:
                    break
            if time.perf_counter() > end:
                break

    def _search_tick(self):
        doc = self.model.doc
        if doc is None or getattr(doc, "is_closed", False):
            return self._search_timer.stop()
        self._scan_some(0.03)
        if not self._scanning():
            self._search_timer.stop()
        if self.hits and self.hit_idx < 0:      # lúc bấm tìm chưa thấy gì, giờ mới thấy: tới kết quả đầu tiên
            k = bisect.bisect_left(self.hit_pages, getattr(self, "_scan_from", 0))
            self.hit_idx = 0 if k >= len(self.hits) else k
            self.ensure_visible(*self.hits[self.hit_idx])
        self.searchChanged.emit(self._search_label())
        self.viewport().update()

    def _search_label(self) -> str:
        more = "…" if self._scanning() else ""
        if not self.hits:
            return "Đang tìm…" if more else "Không tìm thấy"
        return f"{self.hit_idx + 1}/{len(self.hits)}{more}"

    def search(self, text: str, forward: bool = True) -> str:
        """Tìm chữ. Tài liệu dài không bị đứng máy: tới ngay kết quả gần chỗ đang xem, các trang còn lại dò tiếp ở nền."""
        text = text.strip()
        if not text:
            self._reset_search()
            self.viewport().update()
            return ""
        fresh = text != self.query
        if fresh:
            self._reset_search()
            self.query = text
            n, cur = self.model.page_count, self._cur_page
            self._scan = list(range(cur, n)) + list(range(0, cur))      # từ trang đang xem trở đi, rồi vòng lại đầu
            self._scan_some(0.2)                # tài liệu ngắn thì dò xong luôn trong nhịp này
            self._scan_from = cur
            if not forward:
                self._scan_some(60.0)           # tìm ngược: phải dò hết mới biết kết quả đứng ngay trước
            if self.hits:  # bắt đầu từ trang đang xem
                nxt = bisect.bisect_left(self.hit_pages, cur)
                nxt = 0 if nxt >= len(self.hits) else nxt
                self.hit_idx = nxt - 1 if forward else nxt
            if self._scanning():
                self._search_timer.start()
        if not self.hits:
            self.viewport().update()
            return self._search_label()
        step = 1 if forward else -1
        if self._scanning() and not 0 <= self.hit_idx + step < len(self.hits):
            self._scan_some(60.0)               # sắp vòng qua phần chưa dò: dò nốt cho khỏi sót
            self._search_timer.stop()
        self.hit_idx = (self.hit_idx + step) % len(self.hits)
        pg, r = self.hits[self.hit_idx]
        self.ensure_visible(pg, r)
        self.viewport().update()
        return self._search_label()
