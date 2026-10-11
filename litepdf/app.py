"""Cửa sổ chính của PDF Editor Lite."""
from __future__ import annotations

import inspect
import os
import sys
import tempfile
from pathlib import Path

import pymupdf
from PySide6.QtCore import QEvent, QEventLoop, QObject, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (QAction, QActionGroup, QColor, QCursor, QIcon, QImage, QKeySequence, QPainter, QPalette, QPixmap)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QColorDialog, QComboBox, QDoubleSpinBox,
                               QFileDialog, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMainWindow, QMessageBox, QProgressDialog, QSizePolicy, QSpinBox,
                               QSplitter, QSplitterHandle, QStackedWidget, QTabWidget, QToolBar, QToolButton, QVBoxLayout,
                               QWidget)

from . import tools
from .dialogs import (Config, ImagesToPdfDialog, MergeDialog, ReportDialog, SplitDialog, SignatureLibrary, SignDialog, form_dialog, trust_dir)
from .bookmarks import BookmarkPanel
from .icons import apply_menu_icons, icon
from .viewer import DocModel, Viewer

APP_NAME = "PDF Editor Lite"
VERSION = "1.0.0"
AUTHOR = "ngthhung"
DEFAULT_SIZE = (1100, 720)  # kích thước cửa sổ khi mở app
OPEN_FILTER = ("Tất cả file hỗ trợ (*.pdf *.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp *.doc *.docx *.xls "
               "*.xlsx *.ppt *.pptx *.odt *.ods *.odp *.rtf *.txt *.html *.htm *.epub *.xps *.svg);;"
               "PDF (*.pdf);;Ảnh (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp);;"
               "Office (*.doc *.docx *.xls *.xlsx *.ppt *.pptx *.odt *.ods *.odp *.rtf);;Tất cả (*)")
IMG_FILTER = "Ảnh (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp)"
TOPDF_FILTER = ("Ảnh và file văn phòng (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp *.doc *.docx *.xls *.xlsx "
                "*.ppt *.pptx *.odt *.ods *.odp *.rtf *.txt *.html *.htm *.epub *.xps *.svg);;"
                "Ảnh (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp);;"
                "Word (*.doc *.docx *.odt *.rtf);;Excel (*.xls *.xlsx *.ods);;PowerPoint (*.ppt *.pptx *.odp);;Tất cả (*)")

# Bảng phím tắt của toàn bộ chức năng (tên mục menu -> phím)
SHORTCUTS = {
    # Tệp
    "Mở…": "Ctrl+O", "PDF trắng mới": "Ctrl+N", "Ảnh / Word / Excel / PowerPoint → PDF…": "Ctrl+Shift+O",
    "Ghép nhiều ảnh thành một PDF…": "Ctrl+Shift+I", "Gộp nhiều file thành một PDF…": "Ctrl+Shift+M",
    "Lưu": "Ctrl+S", "Lưu thành…": "Ctrl+Shift+S", "In…": "Ctrl+P", "Thông tin tài liệu": "Ctrl+D",
    "Đóng tab": "Ctrl+W", "Thoát": "Ctrl+Q",
    # Sửa
    "Hoàn tác": "Ctrl+Z", "Làm lại": "Ctrl+Y", "Sao chép chữ / hình ảnh đang chọn": "Ctrl+C",
    "Lưu hình ảnh đang chọn thành file…": "Ctrl+Alt+S", "Xoá hình ảnh đang chọn khỏi trang": "Del",
    "Tìm…": "Ctrl+F", "Tìm tiếp": "F3", "Tìm ngược lại": "Shift+F3", "Xoá ghi chú/ảnh đang chọn": "Del",
    "Làm phẳng ghi chú (gắn chết vào trang)": "Ctrl+Shift+F",
    # Xem
    "Phóng to": "Ctrl++", "Thu nhỏ": "Ctrl+-", "Kích thước thật (100%)": "Ctrl+0", "Vừa chiều rộng": "Ctrl+1",
    "Vừa cả trang": "Ctrl+2", "Hiện thanh bên (trang, bookmark)": "F4", "Ẩn thanh bên (trang, bookmark)": "F4", "So sánh song song hai tài liệu (gốc – dịch)": "F6",
    "Bật/tắt cuộn đồng bộ khi so sánh": "F7", "Toàn màn hình": "F11",
    # Trang
    "Xoay trái 90°": "Ctrl+Shift+L", "Xoay phải 90°": "Ctrl+Shift+R", "Xoá trang đang chọn": "Ctrl+Shift+Del",
    "Nhân đôi trang": "Ctrl+Shift+D",
    "Chuyển trang lên trước": "Ctrl+Shift+Up", "Chuyển trang xuống sau": "Ctrl+Shift+Down",
    "Chèn trang trắng sau trang này": "Ctrl+Shift+N", "Chèn file khác vào sau trang này…": "Ctrl+Alt+I",
    "Đánh số trang…": "Ctrl+Alt+N", "Đóng dấu chìm (watermark)…": "Ctrl+Alt+W",
    # Công cụ (một phím, không cần giữ Ctrl)
    "Bàn tay (di chuyển, chọn ghi chú)": "H", "Chọn chữ / hình ảnh": "V", "Sửa chữ gốc": "E", "Thêm chữ": "T",
    "Chèn ảnh": "I", "Xoá trắng một vùng": "X", "Tô sáng": "M", "Gạch chân": "U", "Gạch ngang": "K",
    "Ghi chú dán": "N", "Hình chữ nhật": "R", "Hình elip": "O", "Đường thẳng": "L", "Mũi tên": "A", "Vẽ tự do": "P",
    # Bookmark
    "Thêm bookmark tại vị trí đang xem": "Ctrl+B", "Thêm bookmark con của mục đang chọn": "Ctrl+Shift+B",
    "Tự tạo bookmark từ các tiêu đề…": "Ctrl+Alt+B",
    "Tạo bookmark cho từng trang": "Ctrl+Alt+P", "Xoá tất cả bookmark": "Ctrl+Alt+X",
    # Chuyển đổi
    "Dịch tài liệu sang ngôn ngữ khác…": "Ctrl+Alt+L", "Rà soát / sửa câu dịch của trang này…": "Ctrl+Alt+G", "PDF → Word (.docx)…": "Ctrl+Alt+D", "PDF → Excel (.xlsx)…": "Ctrl+Alt+E", "PDF → Ảnh (PNG/JPG)…": "Ctrl+Alt+J",
    "PDF → Văn bản (.txt)…": "Ctrl+Alt+T", "Xuất mọi hình ảnh trong PDF ra thư mục…": "Ctrl+Alt+M",
    "PDF → HTML…": "Ctrl+Alt+H", "Tách file PDF…": "Ctrl+Shift+T", "Nhận dạng chữ (OCR) cho bản scan…": "Ctrl+Alt+O",
    "Nén giảm dung lượng…": "Ctrl+Alt+C",
    # Ký & Bảo mật
    "Ký số (chọn vị trí hiện chữ ký)…": "Ctrl+Shift+K", "Ký số không hiện khung chữ ký…": "Ctrl+Alt+K",
    "Kiểm tra chữ ký số": "Ctrl+Shift+V", "Chèn ảnh chữ ký tay / con dấu…": "Ctrl+Shift+H",
    "Đặt mật khẩu cho file…": "Ctrl+Shift+P", "Gỡ mật khẩu": "Ctrl+Shift+U",
    "Mở thư mục chứng thư gốc tin cậy": "Ctrl+Alt+R",
    # Trợ giúp
    "Hướng dẫn sử dụng": "F1", "Danh sách phím tắt": "Ctrl+F1", "Giới thiệu": "Shift+F1",
}
SHOW_ONLY = {"Xoá hình ảnh đang chọn khỏi trang", "Xoá ghi chú/ảnh đang chọn"}


# -------------------------------------------------------------------- thanh bên
class ThumbList(QListWidget):
    reordered = Signal(list)

    def __init__(self):
        super().__init__()
        self.setIconSize(QSize(112, 150))
        self.setSpacing(4)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setUniformItemSizes(False)
        self.setStyleSheet("QListWidget{background:#f1f3f4;border:none;} QListWidget::item{color:#3c4043;}"
                           "QListWidget::item:selected{background:#c8dcfb;color:#000;}")

    def dropEvent(self, e):
        super().dropEvent(e)
        order = [self.item(i).data(Qt.UserRole) for i in range(self.count())]
        if order != sorted(order):
            QTimer.singleShot(0, lambda: self.reordered.emit(order))


class _ResetHandle(QSplitterHandle):
    def mouseDoubleClickEvent(self, e):
        self.splitter().reset_sizes()


class ResetSplitter(QSplitter):
    """Thanh chia kéo được; nhấp đúp vào thanh chia thì trả về độ rộng mặc định."""

    def __init__(self, orientation, default):
        super().__init__(orientation)
        self.default = default          # hàm trả về danh sách độ rộng mặc định
        self.setHandleWidth(6)

    def createHandle(self):
        h = _ResetHandle(self.orientation(), self)
        h.setToolTip("Kéo để chỉnh độ rộng · nhấp đúp để về mặc định")
        return h

    def reset_sizes(self):
        self.setSizes(self.default())


SIDE_WIDTH = 210
PANE_MIN = 260      # độ rộng nhỏ nhất của mỗi bên khi so sánh song song (hai bên bằng nhau)


class DocTab(QWidget):
    def __init__(self, model: DocModel, main: "MainWindow"):
        super().__init__()
        self.own_model = model
        self.main = main
        self.own_viewer = Viewer(model)
        self.thumbs = ThumbList()
        self.bookmarks = BookmarkPanel(model, self.own_viewer, main.cfg)
        self.bookmarks.host = (main, self)
        self.bookmarks.hide_side = lambda: (self.side.setVisible(False), main._side_label())
        self.side = QTabWidget()
        self.side.setDocumentMode(True)
        self.side.addTab(self.thumbs, "Trang")
        self.side.addTab(self.bookmarks, "Bookmark")
        self.side.currentChanged.connect(lambda *_: self.bookmarks.resync())
        self.side.setMinimumWidth(190)
        self.partner: Viewer | None = None      # khung xem tài liệu thứ hai khi so sánh song song
        self.partner_tab: DocTab | None = None
        self.source_tab: DocTab | None = None   # tab bản gốc (nếu tab này là bản dịch)
        self.tr_state: dict | None = None       # bản gốc + các cặp câu của lần dịch tạo ra tab này (để rà soát)
        self.active = self.own_viewer
        self.sync = True
        self._syncing = False
        self.own_head = QLabel()
        self.own_head.hide()
        self.own_head.setMinimumWidth(0)
        self.own_head.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        own_box = QWidget()
        own_box.setMinimumWidth(PANE_MIN)
        bl = QVBoxLayout(own_box)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)
        bl.addWidget(self.own_head)
        bl.addWidget(self.own_viewer)
        self.pair = ResetSplitter(Qt.Horizontal, lambda: [max(200, self.pair.width() // 2)] * self.pair.count())
        self.pair.setChildrenCollapsible(False)
        self.pair.addWidget(own_box)
        self.own_viewer.installEventFilter(self)
        self.own_viewer.viewport().installEventFilter(self)
        sp = ResetSplitter(Qt.Horizontal, lambda: [SIDE_WIDTH, max(200, sp.width() - SIDE_WIDTH)])
        self.split = sp
        sp.addWidget(self.side)
        sp.addWidget(self.pair)
        sp.setStretchFactor(1, 1)
        sp.setSizes([SIDE_WIDTH, 900])
        sp.setChildrenCollapsible(False)        # kéo thanh chia không làm mất hẳn thanh bên hay khung xem trang
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(sp)
        self._pending: list[int] = []
        self._timer = QTimer(self, interval=0, timeout=self._fill_thumbs)
        self.blank = QPixmap(112, 150)
        self.blank.fill(Qt.white)
        self.thumbs.itemClicked.connect(lambda it: self.goto_both(self.thumbs.row(it)))
        self.thumbs.reordered.connect(self._reorder)
        self.thumbs.setContextMenuPolicy(Qt.CustomContextMenu)
        self.thumbs.customContextMenuRequested.connect(lambda pos: main.page_menu.exec(self.thumbs.mapToGlobal(pos)))
        self.own_viewer.pageChanged.connect(self._sync_thumb)
        model.changed.connect(self._on_changed)
        self.rebuild()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.side.setMaximumWidth(max(self.side.minimumWidth(), self.width() // 2))   # thanh bên tối đa nửa cửa sổ

    def rebuild(self):
        self._timer.stop()
        self.thumbs.clear()
        n = self.own_model.page_count
        for i in range(n):
            it = QListWidgetItem(QIcon(self.blank), str(i + 1))
            it.setData(Qt.UserRole, i)
            it.setTextAlignment(Qt.AlignCenter)
            self.thumbs.addItem(it)
        self._pending = list(range(n))
        self._timer.start()
        self._sync_thumb(self.own_viewer.current_page())
        self.bookmarks.load()

    def _thumb(self, i: int) -> QIcon:
        page = self.own_model.doc[i]
        r = page.rect
        s = min(112 / max(1, r.width), 150 / max(1, r.height)) * self.devicePixelRatioF()
        pix = page.get_pixmap(matrix=pymupdf.Matrix(s, s), alpha=False)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
        p = QPainter(img)
        p.setPen(QColor("#b0b6be"))
        p.drawRect(0, 0, img.width() - 1, img.height() - 1)
        p.end()
        pm = QPixmap.fromImage(img)
        pm.setDevicePixelRatio(self.devicePixelRatioF())
        return QIcon(pm)

    def _fill_thumbs(self):
        for _ in range(6):
            if not self._pending:
                self._timer.stop()
                return
            i = self._pending.pop(0)
            if i < self.thumbs.count():
                try:
                    self.thumbs.item(i).setIcon(self._thumb(i))
                except Exception:
                    pass

    def _on_changed(self, page, structure):
        if page == "toc":
            if not self.bookmarks.committing:
                self.bookmarks.load()
            return
        if structure or page is None or self.thumbs.count() != self.own_model.page_count:
            self.rebuild()
        elif page not in self._pending:
            self._pending.insert(0, page)
            self._timer.start()

    def _sync_thumb(self, i: int):
        if len(self.thumbs.selectedItems()) <= 1 and 0 <= i < self.thumbs.count():
            self.thumbs.clearSelection()         # không để sót trang được chọn từ trước
            self.thumbs.setCurrentRow(i)

    def _reorder(self, order: list):
        try:
            with self.own_model.edit(structure=True):
                self.own_model.doc.select(order)
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"Không sắp xếp lại được trang:\n{e}")
            self.rebuild()

    def selected_pages(self) -> list[int]:
        if self.active is not self.own_viewer:
            return [self.active.current_page()]
        rows = sorted(self.thumbs.row(it) for it in self.thumbs.selectedItems())
        return rows if rows else [self.own_viewer.current_page()]

    # ------------------------------------------------------------ so sánh song song
    @property
    def viewer(self) -> Viewer:
        """Khung xem đang được thao tác (bên vừa bấm chuột vào khi so sánh song song)."""
        return self.active

    @property
    def model(self) -> DocModel:
        return self.active.model

    def eventFilter(self, obj, e):
        if e.type() in (QEvent.MouseButtonPress, QEvent.FocusIn, QEvent.Wheel) and self.partner is not None:
            for v in (self.own_viewer, self.partner):
                if obj is v or obj is v.viewport():
                    self.set_active(v)
        return False

    def goto_both(self, i: int):
        """Tới trang i; đang so sánh song song (và bật cuộn đồng bộ) thì cả hai bên cùng tới trang đó."""
        if self.partner is None or not self.sync:
            return self.own_viewer.goto_page(i)
        self._syncing = True
        try:
            for v in (self.own_viewer, self.partner):
                v.goto_page(i)
        finally:
            self._syncing = False

    def set_active(self, v: Viewer):
        if v is self.active or v not in (self.own_viewer, self.partner):
            return
        self.active = v
        self._paint_heads()
        self.main._update_ui()

    def _paint_heads(self):
        if self.partner is None:
            return
        for head, v, kind in ((self.partner_head, self.partner, self.kinds[0]), (self.own_head, self.own_viewer, self.kinds[1])):
            on = v is self.active
            m = v.model
            head.setText(f" {kind}: {'● ' if m.dirty else ''}{m.title}" + ("   —  đang thao tác bên này" if on else ""))
            head.setStyleSheet("QLabel{padding:4px 6px;font-weight:%s;color:%s;background:%s;border-bottom:2px solid %s;}"
                               % (("600", "#ffffff", "#1a73e8", "#1a73e8") if on else ("400", "#3c4043", "#e8eaed", "#c4c7cc")))

    def start_compare(self, other: "DocTab", kinds=("Bản gốc", "Bản dịch")):
        """Hiện tài liệu của tab `other` ở bên trái, tài liệu của tab này ở bên phải. Cả hai bên đều sửa được."""
        self.stop_compare()
        self.kinds = kinds
        v = Viewer(other.own_model)
        self.main.wire_viewer(self, v)
        self.partner_head = QLabel()
        self.partner_head.setMinimumWidth(0)
        self.partner_head.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        box = QWidget()
        box.setMinimumWidth(PANE_MIN)
        bl = QVBoxLayout(box)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)
        bl.addWidget(self.partner_head)
        bl.addWidget(v)
        self.pair.insertWidget(0, box)
        self.partner_box, self.partner, self.partner_tab = box, v, other
        v.installEventFilter(self)
        v.viewport().installEventFilter(self)
        self.own_head.show()
        self._side_was = self.side.isVisible()
        self.side.hide()                         # nhường chỗ cho hai trang đứng cạnh nhau
        w = max(200, self.pair.width() // 2)
        self.pair.setSizes([w, w])
        for a, b in ((v, self.own_viewer), (self.own_viewer, v)):
            a.verticalScrollBar().valueChanged.connect(lambda *_, a=a, b=b: self._follow(a, b))
            a.horizontalScrollBar().valueChanged.connect(lambda *_, a=a, b=b: self._follow(a, b))
            a.zoomChanged.connect(lambda *_, a=a, b=b: self._follow_zoom(a, b))
        other.own_model.stateChanged.connect(self._paint_heads)
        self.own_model.stateChanged.connect(self._paint_heads)
        self._paint_heads()
        QTimer.singleShot(0, self._fit_both)

    def _fit_both(self):
        if self.partner is None:
            return
        page = self.own_viewer.current_page()
        self._syncing = True
        try:
            for v in (self.partner, self.own_viewer):
                v.set_fit("width")
                v.goto_page(page)
        finally:
            self._syncing = False

    def _follow(self, a: Viewer, b: Viewer):
        """Cuộn bên này thì bên kia cuộn theo đúng vị trí tương ứng."""
        if not self.sync or self._syncing or self.partner is None:
            return
        self._syncing = True
        try:
            for bar_a, bar_b in ((a.verticalScrollBar(), b.verticalScrollBar()),
                                 (a.horizontalScrollBar(), b.horizontalScrollBar())):
                if bar_a.maximum() == bar_b.maximum():
                    bar_b.setValue(bar_a.value())
                elif bar_a.maximum() > 0:
                    bar_b.setValue(round(bar_a.value() / bar_a.maximum() * bar_b.maximum()))
        finally:
            self._syncing = False

    def _follow_zoom(self, a: Viewer, b: Viewer):
        if not self.sync or self._syncing or self.partner is None:
            return
        self._syncing = True
        try:
            if a.fit:
                b.set_fit(a.fit)
            elif abs(b.zoom - a.zoom) > 1e-6:
                b.set_zoom(a.zoom)
        finally:
            self._syncing = False
        self._follow(a, b)

    def stop_compare(self):
        if self.partner is None:
            return
        v, box, other = self.partner, self.partner_box, self.partner_tab
        self.partner = self.partner_tab = None
        self.active = self.own_viewer
        for m in (other.own_model, self.own_model):
            try:
                m.stateChanged.disconnect(self._paint_heads)
            except (RuntimeError, TypeError):
                pass
        try:
            v.model.changed.disconnect(v._on_changed)
        except (RuntimeError, TypeError):
            pass
        box.setParent(None)
        box.deleteLater()
        self.own_head.hide()
        self.side.setVisible(getattr(self, "_side_was", True))
        self.main._update_ui()


class TranslateWorker(QThread):
    """Gọi bộ máy dịch ở luồng riêng để cửa sổ không bị đơ trong lúc chờ mạng."""
    progress = Signal(int, int, str)

    def __init__(self, engine, texts, opts):
        super().__init__()
        self.engine, self.texts, self.opts = engine, texts, opts
        self.result: list | None = None
        self.error = ""
        self.cancelled = False

    def run(self):
        from . import translate as T
        try:
            self.result = self.engine.translate_many(
                self.texts, self.opts["target"], self.opts["source"],
                progress=lambda a, b, note: self.progress.emit(a, b, note),
                domain=self.opts["domain"], glossary=self.opts["glossary"], context=self.opts.get("context", ""))
        except T.Cancelled:
            self.cancelled = True
        except T.TranslateError as e:
            self.error = str(e)
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"


class HoverMenus(QObject):
    """Mở menu ngay khi rê chuột vào tên menu trên thanh menu (không cần bấm);
    rê chuột ra khỏi cả thanh menu lẫn menu đang mở một lúc thì menu tự đóng."""

    def __init__(self, menubar, close_delay_ms: int = 450):
        super().__init__(menubar)
        self.mb = menubar
        self.mb.setMouseTracking(True)
        self.mb.installEventFilter(self)
        self.timer = QTimer(self, interval=150, timeout=self._check_leave)
        self.away_ms = 0
        self.close_delay = close_delay_ms

    def eventFilter(self, obj, e):
        if obj is self.mb and e.type() == QEvent.MouseMove and not e.buttons():
            act = self.mb.actionAt(e.position().toPoint())
            if act is not None and act.menu() is not None and act.isEnabled() and not act.menu().isVisible():
                if QApplication.activeModalWidget() is None:
                    self.mb.setActiveAction(act)   # thanh menu tự bật menu của mục đang kích hoạt
                    self.away_ms = 0
                    self.timer.start()
        return False

    def _open_menus(self):
        out = []   # chỉ tính menu của thanh menu và menu con của chúng, không đụng tới menu chuột phải

        def walk(menu):
            if menu.isVisible():
                out.append(menu)
            for a in menu.actions():
                if a.menu() is not None:
                    walk(a.menu())
        for act in self.mb.actions():
            if act.menu() is not None:
                walk(act.menu())
        return out

    def _check_leave(self):
        menus = self._open_menus()
        if not menus:
            self.timer.stop()
            return
        pos = QCursor.pos()
        inside = self.mb.rect().contains(self.mb.mapFromGlobal(pos)) or any(
            m.geometry().adjusted(-12, -12, 12, 12).contains(pos) for m in menus)
        self.away_ms = 0 if inside else self.away_ms + self.timer.interval()
        if self.away_ms >= self.close_delay:
            self.timer.stop()
            for m in menus:
                m.close()
            self.mb.setActiveAction(None)


# ------------------------------------------------------------------ cửa sổ chính
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = Config()
        self.setWindowTitle(APP_NAME)
        self.resize(DEFAULT_SIZE[0], DEFAULT_SIZE[1])
        self.setAcceptDrops(True)
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._tab_changed)
        welcome = QLabel(
            f"<div style='text-align:center'><p style='font-size:26px;color:#3c4043'><b>{APP_NAME}</b></p>"
            f"<p style='font-size:12px;color:#80868b'>{APP_NAME} by {AUTHOR} · phiên bản {VERSION}</p>"
            "<p style='font-size:14px;color:#5f6368'>Kéo thả file PDF, ảnh hoặc Word/Excel vào đây<br>"
            "hoặc bấm <b>Ctrl+O</b> để mở file.</p></div>")
        welcome.setAlignment(Qt.AlignCenter)
        self.stack = QStackedWidget()
        self.stack.addWidget(welcome)
        self.stack.addWidget(self.tabs)
        self.setCentralWidget(self.stack)
        self.doc_actions: list[QAction] = []
        self.acts: dict[str, list[QAction]] = {}
        self.tool_actions: dict[str, QAction] = {}
        self._build_actions()
        self._apply_icons()
        self.hover_menus = HoverMenus(self.menuBar())
        self._build_toolbars()
        self.statusBar().showMessage("Sẵn sàng")
        self._update_ui()

    def place_centered(self):
        """Đặt cửa sổ về kích thước mặc định (không vượt quá màn hình) và canh giữa màn hình."""
        from PySide6.QtGui import QCursor, QGuiApplication
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()  # vùng trống, đã trừ thanh tác vụ
        w = min(DEFAULT_SIZE[0], area.width() - 40)
        h = min(DEFAULT_SIZE[1], area.height() - 60)
        self.resize(w, h)
        frame_h = 32  # ước lượng thanh tiêu đề để cả khung cửa sổ nằm giữa
        self.move(area.x() + (area.width() - w) // 2, area.y() + max(0, (area.height() - h - frame_h) // 2))

    # ---------------------------------------------------------------- tiện ích
    def tab(self) -> DocTab | None:
        w = self.tabs.currentWidget()
        return w if isinstance(w, DocTab) else None

    def msg(self, text: str, ms: int = 8000):
        if text:
            self.statusBar().showMessage(text, ms)

    def error(self, text: str):
        QMessageBox.warning(self, APP_NAME, text)

    def info(self, text: str):
        QMessageBox.information(self, APP_NAME, text)

    def guard(self, fn):
        """Bọc một thao tác: bắt lỗi và báo bằng hộp thoại thay vì làm treo ứng dụng."""
        try:
            params = list(inspect.signature(fn).parameters)
        except (TypeError, ValueError):
            params = []

        def run(*_a):
            if params and params[0] == "t":
                t = self.tab()
                if not t:
                    return
                args = (t,)
            else:
                args = ()
            try:
                fn(*args)
            except (tools.PdfError, PermissionError) as e:
                QApplication.restoreOverrideCursor()
                self.error(str(e))
            except Exception as e:
                while QApplication.overrideCursor():
                    QApplication.restoreOverrideCursor()
                self.error(f"Có lỗi xảy ra:\n{type(e).__name__}: {e}")
        return run

    def busy(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()

    def done(self):
        while QApplication.overrideCursor():
            QApplication.restoreOverrideCursor()

    def progress(self, title: str):
        dlg = QProgressDialog(title, None, 0, 100, self)
        dlg.setWindowTitle(APP_NAME)
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(300)

        def cb(i, n):
            dlg.setMaximum(n)
            dlg.setValue(i)
            QApplication.processEvents()
        return dlg, cb

    def _act(self, text, fn, shortcut=None, ic=None, doc=True, tip=None, menu=None, guard=True):
        a = QAction(text, self)
        self.acts.setdefault(text, []).append(a)
        if ic:
            a.setIcon(icon(ic))
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.setToolTip((tip or text.replace("…", "").replace("&", "")) + (f"  ({shortcut})" if shortcut else ""))
        a.triggered.connect(self.guard(fn) if guard else (lambda *_: fn()))
        if doc:
            self.doc_actions.append(a)
        if menu is not None:
            menu.addAction(a)
        return a

    def _out_path(self, t: DocTab, suffix: str, ext: str, filt: str) -> str | None:
        base = Path(t.model.path) if t.model.path else Path(self.cfg.get("last_dir", str(Path.home()))) / t.model.title
        default = str(base.with_name(base.stem + suffix + ext))
        p, _ = QFileDialog.getSaveFileName(self, "Lưu thành", default, filt)
        if p and not p.lower().endswith(ext):
            p += ext
        return p or None

    def _temp_pdf(self, t: DocTab) -> str:
        fd, tmp = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        Path(tmp).write_bytes(t.model.export_bytes())
        return tmp

    # ---------------------------------------------------------------- hành động
    def _build_actions(self):
        mb = self.menuBar()
        A = self._act
        # --- Tệp
        m = mb.addMenu("&Tệp")
        self.a_open = A("Mở…", self.open_dialog, "Ctrl+O", "open", doc=False, menu=m, tip="Mở PDF hoặc tạo PDF từ ảnh/Word/Excel")
        A("PDF trắng mới", self.new_blank, "Ctrl+N", doc=False, menu=m)
        self.recent_menu = m.addMenu("Mở gần đây")
        self.recent_menu.aboutToShow.connect(self._fill_recent)
        m.addSeparator()
        A("Ảnh / Word / Excel / PowerPoint → PDF…", self.convert_dialog, doc=False, menu=m,
          tip="Chọn ảnh hoặc file Word, Excel, PowerPoint để tạo thành PDF")
        A("Ghép nhiều ảnh thành một PDF…", self.images_to_pdf, doc=False, menu=m)
        self.a_merge = A("Gộp nhiều file thành một PDF…", self.merge, None, "merge", doc=False, menu=m)
        m.addSeparator()
        self.a_save = A("Lưu", self.save, "Ctrl+S", "save", menu=m)
        A("Lưu thành…", self.save_as, "Ctrl+Shift+S", menu=m)
        self.a_print = A("In…", self.print_doc, "Ctrl+P", "print", menu=m)
        A("Thông tin tài liệu", self.doc_info, "Ctrl+D", menu=m)
        m.addSeparator()
        A("Đóng tab", lambda: self.close_tab(self.tabs.currentIndex()), "Ctrl+W", menu=m, guard=False)
        A("Thoát", self.close, "Ctrl+Q", doc=False, menu=m, guard=False)
        # --- Sửa
        m = mb.addMenu("&Sửa")
        self.a_undo = A("Hoàn tác", self.undo, "Ctrl+Z", "undo", menu=m)
        self.a_redo = A("Làm lại", self.redo, "Ctrl+Y", "redo", menu=m)
        m.addSeparator()
        A("Sao chép chữ / hình ảnh đang chọn", lambda t: t.viewer.copy_selection(), "Ctrl+C", menu=m)
        A("Lưu hình ảnh đang chọn thành file…", lambda t: t.viewer.save_image(), menu=m)
        A("Xoá hình ảnh đang chọn khỏi trang", lambda t: t.viewer.delete_image(), menu=m)
        A("Tìm…", lambda: (self.search_box.setFocus(), self.search_box.selectAll()), "Ctrl+F", menu=m, guard=False)
        A("Tìm tiếp", lambda: self.do_search(True), "F3", menu=m, guard=False)
        A("Tìm ngược lại", lambda: self.do_search(False), "Shift+F3", menu=m, guard=False)
        m.addSeparator()
        A("Xoá ghi chú/ảnh đang chọn", lambda t: t.viewer.delete_selected_annot(), menu=m)
        A("Làm phẳng ghi chú (gắn chết vào trang)", self.flatten, menu=m)
        # --- Xem
        m = mb.addMenu("&Xem")
        self.a_zin = A("Phóng to", lambda t: t.viewer.set_zoom(t.viewer.zoom * 1.2), "Ctrl++", "zoomin", menu=m)
        self.a_zout = A("Thu nhỏ", lambda t: t.viewer.set_zoom(t.viewer.zoom / 1.2), "Ctrl+-", "zoomout", menu=m)
        A("Kích thước thật (100%)", lambda t: t.viewer.set_zoom(1.0), "Ctrl+0", menu=m)
        self.a_fitw = A("Vừa chiều rộng", lambda t: t.viewer.set_fit("width"), "Ctrl+1", "fitw", menu=m)
        self.a_fitp = A("Vừa cả trang", lambda t: t.viewer.set_fit("page"), "Ctrl+2", "fitp", menu=m)
        m.addSeparator()
        self.a_side = A("Hiện thanh bên (trang, bookmark)", self.side_toggle, "F4", "sidebar", menu=m)
        m.addSeparator()
        self.a_cmp = A("So sánh song song hai tài liệu (gốc – dịch)", self.compare, "F6", "compare", menu=m,
                       tip="Đặt bản gốc và bản dịch cạnh nhau để rà soát; sửa được trực tiếp ở cả hai bên")
        self.a_sync = A("Bật/tắt cuộn đồng bộ khi so sánh", self.toggle_sync, "F7", "syncscroll", menu=m,
                        tip="Hai bên cuộn và thu phóng cùng nhau; tắt để canh lại vị trí từng bên")
        self.a_cmp.setCheckable(True)
        self.a_sync.setCheckable(True)
        m.addSeparator()
        A("Toàn màn hình", lambda: self.showNormal() if self.isFullScreen() else self.showFullScreen(), "F11",
          doc=False, menu=m, guard=False)
        # --- Trang
        m = mb.addMenu("T&rang")
        self.page_menu = m
        self.a_rotl = A("Xoay trái 90°", lambda t: self.rotate(t, -90), "Ctrl+Shift+L", "rotl", menu=m)
        self.a_rotr = A("Xoay phải 90°", lambda t: self.rotate(t, 90), "Ctrl+Shift+R", "rotr", menu=m)
        self.a_del = A("Xoá trang đang chọn", self.delete_pages, None, "delete", menu=m)
        A("Nhân đôi trang", self.duplicate_page, menu=m)
        A("Chuyển trang lên trước", lambda t: self.move_page(t, -1), "Ctrl+Shift+Up", menu=m)
        A("Chuyển trang xuống sau", lambda t: self.move_page(t, 1), "Ctrl+Shift+Down", menu=m)
        m.addSeparator()
        A("Chèn trang trắng sau trang này", self.insert_blank, menu=m)
        A("Chèn file khác vào sau trang này…", self.insert_file, menu=m)
        m.addSeparator()
        A("Đánh số trang…", self.page_numbers, menu=m)
        A("Đóng dấu chìm (watermark)…", self.watermark, menu=m)
        # --- Công cụ
        m = mb.addMenu("&Công cụ")
        grp = QActionGroup(self)
        defs = [("hand", "Bàn tay (di chuyển, chọn ghi chú)", "hand", "H"), ("select", "Chọn chữ / hình ảnh", "select", "V"), None,
                ("edittext", "Sửa chữ gốc", "edittext", "E"), ("text", "Thêm chữ", "text", "T"),
                ("image", "Chèn ảnh", "image", None), ("erase", "Xoá trắng một vùng", "erase", None), None,
                ("highlight", "Tô sáng", "highlight", None), ("underline", "Gạch chân", "underline", None),
                ("strike", "Gạch ngang", "strike", None), ("note", "Ghi chú dán", "note", None), None,
                ("rect", "Hình chữ nhật", "rect", None), ("ellipse", "Hình elip", "ellipse", None),
                ("line", "Đường thẳng", "line", None), ("arrow", "Mũi tên", "arrow", None), ("ink", "Vẽ tự do", "ink", None)]
        for d in defs:
            if d is None:
                m.addSeparator()
                continue
            key, text, ic, sc = d
            a = QAction(icon(ic), text, self, checkable=True)
            a.setToolTip(text + (f"  ({sc})" if sc else ""))
            if sc:
                a.setShortcut(QKeySequence(sc))
            a.triggered.connect(lambda _=False, k=key: self.pick_tool(k))
            grp.addAction(a)
            m.addAction(a)
            self.tool_actions[key] = a
            self.doc_actions.append(a)
        self.tool_actions["hand"].setChecked(True)
        # --- Chuyển đổi
        # --- Bookmark
        m = mb.addMenu("&Bookmark")
        A("Thêm bookmark tại vị trí đang xem", lambda t: self.bookmark_add(t, False), "Ctrl+B", menu=m)
        A("Thêm bookmark con của mục đang chọn", lambda t: self.bookmark_add(t, True), "Ctrl+Shift+B", menu=m)
        m.addSeparator()
        A("Tự tạo bookmark từ các tiêu đề…", self.bookmark_auto, menu=m)
        A("Tạo bookmark cho từng trang", self.bookmark_pages, menu=m)
        A("Xoá tất cả bookmark", self.bookmark_clear, menu=m)
        m = mb.addMenu("C&huyển đổi")
        A("Dịch tài liệu sang ngôn ngữ khác…", self.translate_doc, menu=m)
        A("Rà soát / sửa câu dịch của trang này…", self.review_translation, menu=m,
          tip="Bảng câu gốc – câu dịch của trang đang xem: sửa câu dịch, trang được dựng lại đúng bố cục")
        m.addSeparator()
        A("PDF → Word (.docx)…", self.to_word, menu=m)
        A("PDF → Excel (.xlsx)…", self.to_excel, menu=m)
        A("PDF → Ảnh (PNG/JPG)…", self.to_images, menu=m)
        A("PDF → Văn bản (.txt)…", self.to_text, menu=m)
        A("Xuất mọi hình ảnh trong PDF ra thư mục…", self.export_images, menu=m)
        A("PDF → HTML…", self.to_html, menu=m)
        m.addSeparator()
        self.a_split = A("Tách file PDF…", self.split, None, "split", menu=m)
        A("Nhận dạng chữ (OCR) cho bản scan…", self.ocr, menu=m)
        A("Nén giảm dung lượng…", self.compress, menu=m)
        # --- Ký & bảo mật
        m = mb.addMenu("&Ký && Bảo mật")
        self.a_sign = A("Ký số (chọn vị trí hiện chữ ký)…", lambda t: self.pick_tool("sign"), "Ctrl+Shift+K", "sign", menu=m,
                        tip="Ký số bằng USB token hoặc file .pfx")
        A("Ký số không hiện khung chữ ký…", lambda t: self.do_sign(t, None, None), menu=m)
        self.a_verify = A("Kiểm tra chữ ký số", self.verify, None, "verify", menu=m)
        m.addSeparator()
        self.a_hand = A("Chèn ảnh chữ ký tay / con dấu…", self.hand_signature, None, "handsign", menu=m)
        m.addSeparator()
        self.a_lock = A("Đặt mật khẩu cho file…", self.set_password, None, "lock", menu=m)
        A("Gỡ mật khẩu", self.remove_password, menu=m)
        A("Mở thư mục chứng thư gốc tin cậy", self.open_trust_dir, doc=False, menu=m)
        # --- Trợ giúp
        m = mb.addMenu("Trợ &giúp")
        A("Hướng dẫn sử dụng", self.show_guide, doc=False, menu=m, guard=False)
        A("Danh sách phím tắt", self.show_shortcuts, doc=False, menu=m, guard=False)
        A("Giới thiệu", self.about, doc=False, menu=m, guard=False)
        self._apply_shortcuts()

    def _apply_shortcuts(self):
        """Gán phím tắt cho mọi chức năng theo bảng SHORTCUTS (một chỗ duy nhất để dễ rà soát)."""
        def walk(menu):
            for a in menu.actions():
                if a.isSeparator():
                    continue
                if a.menu():
                    walk(a.menu())
                    continue
                key = SHORTCUTS.get(a.text())
                a.setShortcut(QKeySequence(key) if key else QKeySequence())
                if a.text() in SHOW_ONLY:   # phím do khung xem trang tự xử lý, ở đây chỉ để hiển thị
                    a.setShortcutContext(Qt.WidgetShortcut)
                base = a.toolTip().split("  (")[0]
                a.setToolTip(base + (f"  ({key})" if key else ""))
        for act in self.menuBar().actions():
            if act.menu():
                walk(act.menu())

    def shortcut_table(self) -> list[tuple[str, list[tuple[str, str]]]]:
        out = []
        for act in self.menuBar().actions():
            rows = [(a.text().replace("…", ""), a.shortcut().toString(QKeySequence.NativeText))
                    for a in act.menu().actions() if not a.isSeparator() and not a.menu() and not a.shortcut().isEmpty()]
            if rows:
                out.append((act.text().replace("&&", "\x00").replace("&", "").replace("\x00", "&"), rows))
        return out

    def show_guide(self):
        """Hướng dẫn sử dụng, kèm tình trạng các thành phần tuỳ chọn trên máy này."""
        from . import guide, ocr
        from . import translate as T
        from .dialogs import data_dir
        import importlib.util
        st = {"frozen": tools.FROZEN, "data_dir": data_dir(), "gemini": bool(self.cfg.get("gemini_key")),
              "add": "Chạy lại bộ cài PDF Editor Lite và tích thành phần này." if tools.FROZEN else
                     "Xem mục Nhận dạng chữ (OCR) trong app để cài.",
              "add_ai": "Chạy lại bộ cài và tích “AI dịch chạy trên máy”, hoặc cài Ollama từ ollama.com."}
        for key, fn in (("tess", tools.tess_languages), ("rapid", ocr.rapid_available),
                        ("pdf2docx", lambda: importlib.util.find_spec("pdf2docx") is not None),
                        ("pkcs11", lambda: importlib.util.find_spec("pkcs11") is not None)):
            try:
                st[key] = fn()
            except Exception:
                st[key] = None
        try:
            so = tools.find_soffice()
            st["office"] = "LibreOffice" if so else ("Microsoft Office" if tools.has_ms_office() else "")
        except Exception:
            st["office"] = ""
        try:
            st["local"] = ", ".join(f"{n} ({len(ms)} model)" for n, _b, ms in T.detect_local())
        except Exception:
            st["local"] = ""
        d = ReportDialog(self, "Hướng dẫn sử dụng", guide.guide_html(APP_NAME, VERSION, st))
        from .dialogs import fit_dialog, center_on_parent
        fit_dialog(d, 860, 680)
        center_on_parent(d)
        d.exec()

    def show_shortcuts(self):
        cols = []
        for title, rows in self.shortcut_table():
            body = "".join(f"<tr><td>{n}</td><td style='padding-left:18px'><b>{k}</b></td></tr>" for n, k in rows)
            cols.append(f"<h3 style='margin-bottom:2px'>{title}</h3><table cellpadding='2'>{body}</table>")
        extra = ("<h3 style='margin-bottom:2px'>Trong trang</h3><table cellpadding='2'>"
                 "<tr><td>Phóng to / thu nhỏ bằng chuột</td><td style='padding-left:18px'><b>Ctrl + lăn chuột</b></td></tr>"
                 "<tr><td>Cuộn một màn hình</td><td style='padding-left:18px'><b>Page Up / Page Down / Space</b></td></tr>"
                 "<tr><td>Về trang đầu / trang cuối</td><td style='padding-left:18px'><b>Ctrl+Home / Ctrl+End</b></td></tr>"
                 "<tr><td>Thôi công cụ đang dùng, bỏ chọn</td><td style='padding-left:18px'><b>Esc</b></td></tr>"
                 "<tr><td>Đổi tên bookmark</td><td style='padding-left:18px'><b>F2</b></td></tr></table>")
        d = ReportDialog(self, "Danh sách phím tắt", "".join(cols) + extra)
        d.resize(560, 660)
        d.exec()

    def _apply_icons(self):
        for act in self.menuBar().actions():
            if act.menu():
                apply_menu_icons(act.menu())
                # mỗi lần mở menu: làm mờ những mục lúc này không dùng được; đóng menu thì trả lại
                # (để phím tắt như Ctrl+C không bị khoá theo trạng thái cũ)
                act.menu().aboutToShow.connect(self._dim_unavailable)
                act.menu().aboutToHide.connect(lambda: QTimer.singleShot(0, self._update_ui))

    def _set(self, text: str, on: bool):
        for a in self.acts.get(text, []):
            a.setEnabled(bool(on))

    def _dim_compare(self, t):
        """Các mục chỉ dùng được khi có bản dịch / có tài liệu để so sánh: khoá ngay (cả nút, menu lẫn phím tắt)."""
        comparing = t.partner is not None
        self._set("Rà soát / sửa câu dịch của trang này…", self._review_tab(t) is not None)
        self.a_cmp.setEnabled(comparing or len(self.doc_tabs()) > 1)
        self.a_cmp.setChecked(comparing)
        self.a_sync.setEnabled(comparing)
        self.a_sync.setChecked(comparing and t.sync)

    def _dim_unavailable(self):
        self.recent_menu.setEnabled(any(os.path.exists(p) for p in self.cfg.get("recent", [])))
        t = self.tab()
        self._side_label()
        if not t:
            return
        v, m = t.viewer, t.model
        n, cur = m.page_count, v.current_page()
        has_query = bool(self.search_box.text().strip())
        self._set("Sao chép chữ / hình ảnh đang chọn", v.sel_text or v.sel_image)
        self._set("Lưu hình ảnh đang chọn thành file…", v.sel_image)
        self._set("Xoá hình ảnh đang chọn khỏi trang", v.sel_image)
        self._set("Xoá ghi chú/ảnh đang chọn", v.annot)
        self._set("Tìm tiếp", has_query)
        self._set("Tìm ngược lại", has_query)
        self._set("Chuyển trang lên trước", cur > 0)
        self._set("Chuyển trang xuống sau", cur < n - 1)
        self._set("Thêm bookmark con của mục đang chọn", t.bookmarks.tree.currentItem() is not None)
        self._set("Xoá tất cả bookmark", t.bookmarks.tree.topLevelItemCount() > 0)
        has_annot = getattr(m, "_has_annot", None)
        if has_annot is None:        # dò một lần rồi nhớ; tài liệu thay đổi thì dò lại (xem add_tab)
            has_annot = False
            try:
                for i in range(min(n, 400)):
                    if m.doc[i].first_annot is not None:
                        has_annot = True
                        break
            except Exception:
                has_annot = True
            m._has_annot = has_annot
        self._set("Làm phẳng ghi chú (gắn chết vào trang)", has_annot)
        self._dim_compare(t)
        self._set("Phóng to", v.zoom < 5.99)
        self._set("Thu nhỏ", v.zoom > 0.101)

    def _build_toolbars(self):
        tb = QToolBar("Chính")
        tb.setMovable(False)
        tb.setIconSize(QSize(22, 22))
        self.addToolBar(tb)
        for a in (self.a_open, self.a_save, self.a_print, None, self.a_undo, self.a_redo, None, self.a_side,
                  self.a_cmp, self.a_sync,
                  self.a_zout):
            tb.addSeparator() if a is None else tb.addAction(a)
        self.zoom_box = QComboBox()
        self.zoom_box.setEditable(True)
        self.zoom_box.addItems(["50%", "75%", "100%", "125%", "150%", "200%", "300%", "400%"])
        self.zoom_box.setFixedWidth(84)
        self.zoom_box.setInsertPolicy(QComboBox.NoInsert)
        self.zoom_box.textActivated.connect(self._zoom_typed)
        self.zoom_box.lineEdit().returnPressed.connect(lambda: self._zoom_typed(self.zoom_box.currentText()))
        tb.addWidget(self.zoom_box)
        for a in (self.a_zin, self.a_fitw, self.a_fitp, None):
            tb.addSeparator() if a is None else tb.addAction(a)
        self.page_box = QSpinBox()
        self.page_box.setFixedWidth(70)
        self.page_box.setKeyboardTracking(False)
        self.page_box.valueChanged.connect(self._goto_typed)
        self.page_lb = QLabel(" / 0 ")
        tb.addWidget(QLabel(" Trang "))
        tb.addWidget(self.page_box)
        tb.addWidget(self.page_lb)
        tb.addSeparator()
        for a in (self.a_rotl, self.a_rotr, self.a_del, self.a_merge, self.a_split):
            tb.addAction(a)
        sp = QWidget()
        sp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(sp)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Tìm trong tài liệu…")
        self.search_box.setFixedWidth(210)
        self.search_box.setClearButtonEnabled(True)
        self.search_box.returnPressed.connect(lambda: self.do_search(True))
        self.search_box.textChanged.connect(lambda s: (not s) and self.do_search(True))
        self.search_box.textChanged.connect(lambda *_: self._dim_unavailable())
        tb.addWidget(self.search_box)
        self.search_lb = QLabel("")
        self.search_lb.setMinimumWidth(70)
        tb.addWidget(self.search_lb)

        self.addToolBarBreak()
        t2 = QToolBar("Công cụ")
        t2.setMovable(False)
        t2.setIconSize(QSize(22, 22))
        self.addToolBar(t2)
        order = ["hand", "select", None, "edittext", "text", "image", "erase", None, "highlight", "underline", "strike",
                 "note", None, "rect", "ellipse", "line", "arrow", "ink", None]
        for k in order:
            t2.addSeparator() if k is None else t2.addAction(self.tool_actions[k])
        t2.addWidget(QLabel(" Màu "))
        self.color_btn = QToolButton()
        self.color_btn.setFixedSize(30, 22)
        self.color_btn.setToolTip("Màu của công cụ đang chọn")
        self.color_btn.clicked.connect(self.pick_color)
        t2.addWidget(self.color_btn)
        t2.addWidget(QLabel("  Nét "))
        self.width_box = QDoubleSpinBox()
        self.width_box.setRange(0.5, 12)
        self.width_box.setSingleStep(0.5)
        self.width_box.setValue(1.5)
        self.width_box.setFixedWidth(64)
        self.width_box.valueChanged.connect(lambda v: self.tab() and setattr(self.tab().viewer, "line_width", v))
        t2.addWidget(self.width_box)
        t2.addSeparator()
        for a in (self.a_hand, self.a_sign, self.a_verify, self.a_lock):
            b = QToolButton()
            b.setDefaultAction(a)
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            t2.addWidget(b)
        self.a_hand.setIconText("Chữ ký tay")
        self.a_sign.setIconText("Ký số")
        self.a_verify.setIconText("Kiểm tra chữ ký")
        self.a_lock.setIconText("Mật khẩu")

    # ---------------------------------------------------------------- trạng thái
    def _tab_changed(self, *_):
        self._update_ui()

    def _update_ui(self):
        t = self.tab()
        self.stack.setCurrentIndex(1 if self.tabs.count() else 0)
        self._side_label()
        for a in self.doc_actions:
            a.setEnabled(t is not None)
        if not t:
            self.setWindowTitle(APP_NAME)
            self.page_lb.setText(" / 0 ")
            return
        m = t.model
        self.a_undo.setEnabled(bool(m.undo_stack))
        self.a_redo.setEnabled(bool(m.redo_stack))
        # các mục/nút luôn phản ánh trạng thái tài liệu (cả trên thanh công cụ)
        self.a_save.setEnabled(m.dirty)
        self.a_del.setEnabled(m.page_count > 1)
        self.a_split.setEnabled(m.page_count > 1)
        self.a_verify.setEnabled(bool(getattr(m, "has_sig", False)))
        self._set("Gỡ mật khẩu", m.password)
        self._dim_compare(t)
        self.setWindowTitle(f"{'● ' if m.dirty else ''}{m.title} – {APP_NAME}")
        i = self.tabs.indexOf(t)
        om = t.own_model
        self.tabs.setTabText(i, ("● " if om.dirty else "") + om.title + ("  ⇄" if t.partner is not None else ""))
        self.tabs.setTabToolTip(i, om.path or "Chưa lưu")
        if t.partner_tab is not None:            # sửa bên bản gốc thì tab của bản gốc cũng phải hiện dấu chưa lưu
            pm = t.partner_tab.own_model
            self.tabs.setTabText(self.tabs.indexOf(t.partner_tab), ("● " if pm.dirty else "") + pm.title)
        self.page_box.blockSignals(True)
        self.page_box.setRange(1, max(1, m.page_count))
        self.page_box.setValue(t.viewer.current_page() + 1)
        self.page_box.blockSignals(False)
        self.page_lb.setText(f" / {m.page_count} ")
        self.zoom_box.setEditText(f"{round(t.viewer.zoom * 100)}%")
        a = self.tool_actions.get(t.viewer.tool)
        if a:
            a.setChecked(True)
        else:
            for x in self.tool_actions.values():
                x.setChecked(False)
        self._update_color()
        # Trạng thái mờ/sáng của từng mục luôn được tính lại ở đây (không chờ tới lúc mở menu), để menu hiện đúng ngay
        # từ lần rê chuột đầu tiên và phím tắt của mục không dùng được cũng bị khoá.
        self._dim_unavailable()

    def _update_color(self):
        t = self.tab()
        if t:
            c = t.viewer.colors[t.viewer._color_group()]
            self.color_btn.setStyleSheet(f"QToolButton{{background:{c.name()};border:1px solid #80868b;border-radius:3px;}}")

    def pick_color(self):
        t = self.tab()
        if not t:
            return
        g = t.viewer._color_group()
        c = QColorDialog.getColor(t.viewer.colors[g], self, "Chọn màu")
        if c.isValid():
            t.viewer.colors[g] = c
            self._update_color()

    def _zoom_typed(self, text: str):
        t = self.tab()
        try:
            v = float(text.replace("%", "").replace(",", ".").strip()) / 100
        except ValueError:
            return
        if t and v > 0:
            t.viewer.set_zoom(v)
            t.viewer.setFocus()

    def _goto_typed(self, v: int):
        t = self.tab()
        if t:
            t.viewer.goto_page(v - 1)

    def pick_tool(self, key: str):
        t = self.tab()
        if not t:
            return
        if key == "image":
            p, _ = QFileDialog.getOpenFileName(self, "Chọn ảnh để chèn", self.cfg.get("last_dir", ""), IMG_FILTER)
            if not p:
                self._update_ui()
                return
            t.viewer.set_tool("image", p)
        else:
            t.viewer.set_tool(key)
        t.viewer.setFocus()

    def do_search(self, forward: bool):
        t = self.tab()
        if t:
            self.search_lb.setText(" " + t.viewer.search(self.search_box.text(), forward))

    # ---------------------------------------------------------------- mở / đóng
    def add_tab(self, model: DocModel) -> DocTab:
        t = DocTab(model, self)
        v = t.own_viewer
        self.wire_viewer(t, v)
        model.stateChanged.connect(self._update_ui)
        model.changed.connect(lambda *_: setattr(model, "_has_annot", None))
        def refresh(*_):
            try:
                if self.tab() is t:
                    self._dim_unavailable()
            except RuntimeError:      # cửa sổ đang đóng: các thành phần giao diện đã bị huỷ
                pass
        t.bookmarks.tree.currentItemChanged.connect(refresh)
        t.bookmarks.tree.model().rowsInserted.connect(refresh)
        t.bookmarks.tree.model().rowsRemoved.connect(refresh)
        t.bookmarks.tree.model().modelReset.connect(refresh)
        i = self.tabs.addTab(t, model.title)
        self.tabs.setCurrentIndex(i)
        self._update_ui()
        QTimer.singleShot(0, v.apply_zoom)
        return t

    def wire_viewer(self, t: DocTab, v: Viewer):
        v.message.connect(self.msg)
        v.pageChanged.connect(lambda *_: self._update_ui() if self.tab() is t and t.viewer is v else None)
        v.zoomChanged.connect(lambda *_: self._update_ui() if self.tab() is t and t.viewer is v else None)
        v.toolChanged.connect(lambda *_: self._update_ui() if self.tab() is t and t.viewer is v else None)
        v.signRequested.connect(lambda pg, rect: self.guard(lambda: self.do_sign(t, pg, rect))())
        v.selectionChanged.connect(lambda *_: self._dim_unavailable() if self.tab() is t and t.viewer is v else None)

    # ---------------------------------------------------------------- so sánh song song
    def doc_tabs(self) -> list[DocTab]:
        return [w for w in (self.tabs.widget(i) for i in range(self.tabs.count())) if isinstance(w, DocTab)]

    def compare(self, t: DocTab):
        if t.partner is not None:
            t.stop_compare()
            return self.msg("Đã tắt so sánh song song.")
        others = [x for x in self.doc_tabs() if x is not t]
        if not others:
            return self.info("Cần mở ít nhất hai tài liệu để so sánh.\nVí dụ: mở file gốc, dịch nó (Chuyển đổi → Dịch tài liệu), "
                             "rồi bấm lại mục này.")
        back = [x for x in others if x.source_tab is t]
        if t.source_tab in others:
            return self.start_compare(t, t.source_tab)
        if back:                                  # đang đứng ở bản gốc: chuyển sang tab bản dịch rồi so sánh
            return self.start_compare(back[-1], t)
        other = others[0]
        if len(others) > 1:
            names = [f"{i + 1}. {x.own_model.title}" for i, x in enumerate(others)]
            name, ok = QInputDialog.getItem(self, APP_NAME, f"So sánh “{t.own_model.title}” với tài liệu nào?\n"
                                            "(tài liệu được chọn nằm bên trái)", names, 0, False)
            if not ok:
                return
            other = others[names.index(name)]
        self.start_compare(t, other, ("Tài liệu 1", "Tài liệu 2"))

    def start_compare(self, t: DocTab, other: DocTab, kinds=("Bản gốc", "Bản dịch")):
        self.tabs.setCurrentWidget(t)
        t.start_compare(other, kinds)
        self._update_ui()
        self.msg("Đang so sánh song song. Bấm vào bên nào thì sửa, lưu, hoàn tác… áp dụng cho bên đó. Bấm F6 để tắt.", 15000)

    def toggle_sync(self, t: DocTab):
        t.sync = not t.sync
        if t.sync and t.partner is not None:
            other = t.partner if t.active is t.own_viewer else t.own_viewer
            t._follow_zoom(t.active, other)
        self._update_ui()
        self.msg("Cuộn đồng bộ hai bên: " + ("BẬT" if t.sync else "TẮT (mỗi bên cuộn riêng để canh lại vị trí)"))

    def convert_dialog(self):
        """Tạo PDF từ file không phải PDF (ảnh, Word, Excel, PowerPoint...)."""
        ps, _ = QFileDialog.getOpenFileNames(self, "Chọn file để tạo PDF", self.cfg.get("last_dir", ""), TOPDF_FILTER)
        for p in ps:
            self.open_path(p)

    def open_dialog(self):
        ps, _ = QFileDialog.getOpenFileNames(self, "Mở file", self.cfg.get("last_dir", ""), OPEN_FILTER)
        for p in ps:
            self.open_path(p)

    def open_path(self, path: str) -> DocTab | None:
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            self.error(f"Không tìm thấy file:\n{path}")
            return None
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if w.own_model.path and os.path.normcase(w.own_model.path) == os.path.normcase(path):
                self.tabs.setCurrentIndex(i)
                return w
        self.cfg["last_dir"] = os.path.dirname(path)
        ext = Path(path).suffix.lower()
        self.busy()
        try:
            if ext == ".pdf":
                data = Path(path).read_bytes()
                pw = None
                while True:
                    try:
                        model = DocModel(data, path, pw)
                        break
                    except PermissionError:
                        self.done()
                        pw, ok = QInputDialog.getText(self, "File có mật khẩu",
                                                      ("Mật khẩu chưa đúng, nhập lại:\n" if pw is not None
                                                       else "Nhập mật khẩu để mở:\n") + os.path.basename(path),
                                                      QLineEdit.Password)
                        if not ok:
                            return None
                note = ""
            else:
                data, eng = tools.any_to_pdf_bytes(path)
                model = DocModel(data, None, title=Path(path).stem + ".pdf")
                note = f"Đã tạo PDF từ {os.path.basename(path)}" + (f" bằng {eng}" if eng else "") + ". Bấm Lưu để ghi file."
        except tools.PdfError as e:
            self.done()
            self.error(str(e))
            return None
        except Exception as e:
            self.done()
            self.error(f"Không mở được file:\n{type(e).__name__}: {e}")
            return None
        self.done()
        model.has_sig = b"/ByteRange" in data
        t = self.add_tab(model)
        if ext == ".pdf":
            rec = [p for p in self.cfg.get("recent", []) if p != path]
            self.cfg["recent"] = [path] + rec[:11]
            if model.has_sig:
                note = "Tài liệu này có chữ ký số. Xem tại Ký & Bảo mật → Kiểm tra chữ ký số."
        self.cfg.save()
        self.msg(note or f"Đã mở {os.path.basename(path)} ({model.page_count} trang)")
        return t

    def _fill_recent(self):
        self.recent_menu.clear()
        for p in self.cfg.get("recent", []):
            if os.path.exists(p):
                self.recent_menu.addAction(icon("pdf"), p, lambda p=p: self.open_path(p))
        if self.recent_menu.isEmpty():
            self.recent_menu.addAction("(chưa có)").setEnabled(False)

    def new_blank(self):
        d = pymupdf.open()
        d.new_page(width=595, height=842)
        data = d.tobytes()
        d.close()
        m = DocModel(data, None, title="Tài liệu mới.pdf")
        m.has_sig = False
        self.add_tab(m)

    def images_to_pdf(self):
        dlg = ImagesToPdfDialog(self, self.cfg)
        if not dlg.exec() or not dlg.paths():
            return
        self.cfg.save()
        prog, cb = self.progress("Đang tạo PDF từ ảnh…")
        try:
            data = tools.images_to_pdf(dlg.paths(), progress=cb, **dlg.options())
        finally:
            prog.close()
        m = DocModel(data, None, title="Ảnh ghép.pdf")
        m.has_sig = False
        self.add_tab(m)
        self.msg(f"Đã tạo PDF {m.page_count} trang từ ảnh. Bấm Lưu để ghi file.")

    def maybe_save(self, t: DocTab) -> bool:
        if not t.own_model.dirty:
            return True
        self.tabs.setCurrentWidget(t)
        t.set_active(t.own_viewer)
        r = QMessageBox.question(self, APP_NAME, f"“{t.model.title}” có thay đổi chưa lưu. Lưu lại?",
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Cancel:
            return False
        if r == QMessageBox.Save:
            return self._save(t, t.model.path)
        return True

    def close_tab(self, i: int, force: bool = False):
        t = self.tabs.widget(i)
        if not isinstance(t, DocTab):
            return
        if not force and not self.maybe_save(t):
            return
        t.stop_compare()
        for x in self.doc_tabs():                # tab khác đang so sánh với tài liệu này: tắt so sánh trước khi đóng
            if x.partner_tab is t:
                x.stop_compare()
            if x.source_tab is t:
                x.source_tab = None
        self.tabs.removeTab(i)
        t.own_model.close()
        t.deleteLater()
        self._update_ui()

    def closeEvent(self, e):
        for i in range(self.tabs.count()):
            if not self.maybe_save(self.tabs.widget(i)):
                e.ignore()
                return
        self.cfg.save()
        e.accept()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            if u.isLocalFile():
                self.open_path(u.toLocalFile())

    # ---------------------------------------------------------------- lưu / in
    def _save(self, t: DocTab, path: str | None) -> bool:
        m = t.model
        if not path:
            path = self._out_path(t, "", ".pdf", "PDF (*.pdf)")
            if not path:
                return False
        if getattr(m, "has_sig", False) and m.dirty:
            r = QMessageBox.warning(self, APP_NAME, "Tài liệu này đã có chữ ký số.\nLưu các thay đổi sẽ làm chữ ký số cũ "
                                    "mất hiệu lực.\n\nVẫn lưu?", QMessageBox.Yes | QMessageBox.No)
            if r != QMessageBox.Yes:
                return False
        self.busy()
        try:
            m.save(path)
            m.has_sig = b"/ByteRange" in (m.base_data or b"")
        except Exception as e:
            self.done()
            folder = os.path.dirname(os.path.abspath(path))
            if isinstance(e, PermissionError) or (isinstance(e, FileNotFoundError) and os.path.isdir(folder)):
                why = ("Windows không cho app ghi vào thư mục này. Thường gặp khi thư mục Documents / Desktop / Pictures đang "
                       "được Windows Security bảo vệ (Ransomware protection → Controlled folder access), hoặc file đang mở ở "
                       "chương trình khác, hoặc là thư mục chỉ đọc.")
            elif isinstance(e, FileNotFoundError):
                why = "Thư mục này không còn tồn tại (đã bị đổi tên, chuyển đi hoặc ổ đĩa đã rút ra)."
            else:
                why = "Nếu file đang mở ở chương trình khác, hãy đóng lại rồi thử lại."
            box = QMessageBox(QMessageBox.Warning, APP_NAME, f"Không lưu được file vào:\n{path}\n\n{why}\n\nChi tiết: {e}",
                              parent=self)
            again = box.addButton("Lưu vào thư mục khác…", QMessageBox.AcceptRole)
            box.addButton("Huỷ", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is again:
                return self._save(t, None)
            return False
        self.done()
        self.msg(f"Đã lưu: {path}")
        self._update_ui()
        return True

    def save(self, t):
        self._save(t, t.model.path)

    def save_as(self, t):
        self._save(t, None)

    def undo(self, t):
        if t.model.undo():
            self.msg("Đã hoàn tác")

    def redo(self, t):
        if t.model.redo():
            self.msg("Đã làm lại")

    def print_doc(self, t):
        from .printing import PrintDialog, run_print
        dlg = PrintDialog(self, t.model.doc, t.model.title, t.viewer.current_page(), t.selected_pages(), self.cfg)
        if not dlg.exec():
            return
        self.cfg.save()
        n = run_print(dlg.result_printer, t.model.doc, dlg.result_opts, self)
        if dlg.out_file:
            self.msg(f"Đã lưu bản in: {dlg.out_file}")
        else:
            self.msg(f"Đã gửi {n} tờ tới máy in {dlg.result_printer.printerName()}")

    def doc_info(self, t):
        from html import escape
        m = t.model
        doc = m.doc
        md = doc.metadata or {}
        cur = t.viewer.current_page()
        self.busy()
        try:
            info = tools.document_report(doc, m.base_data, cur)
        finally:
            self.done()
        sec = getattr(m, "security", None) or {}
        size = len(m.base_data) if m.base_data else 0
        stat = ""
        if m.path and os.path.exists(m.path):
            import time
            st = os.stat(m.path)
            stat = time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(st.st_mtime))

        def yes(v):
            return "Có" if v else "Không"

        def perm(k):
            return "Cho phép" if sec.get(k, True) else "Không cho phép"

        sections = [
            ("Tập tin", [
                ("Tên file", m.title), ("Đường dẫn", m.path or "(chưa lưu)"),
                ("Dung lượng", f"{size / 1024 / 1024:.2f} MB ({size:,} byte)".replace(",", ".") if size else "–"),
                ("Sửa lần cuối trên đĩa", stat), ("Trạng thái", "Có thay đổi chưa lưu" if m.dirty else "Đã lưu"),
                ("Phiên bản PDF", info["version"]), ("Tối ưu xem trên web", yes(info["linearized"])),
                ("PDF có gắn thẻ (tagged)", yes(info["tagged"]))]),
            ("Mô tả", [
                ("Tiêu đề", md.get("title")), ("Tác giả", md.get("author")), ("Chủ đề", md.get("subject")),
                ("Từ khoá", md.get("keywords")), ("Tạo bằng", md.get("creator")),
                ("Phần mềm xuất PDF", md.get("producer")),
                ("Ngày tạo", tools.pdf_date(md.get("creationDate"))),
                ("Ngày sửa", tools.pdf_date(md.get("modDate")))]),
            ("Trang", [
                ("Số trang", doc.page_count), ("Khổ trang", info["sizes"]),
                (f"Trang đang xem ({cur + 1})", info["current"]), ("Trang bị xoay", info["rotated"]),
                ("Mục lục (bookmark)", f"{info['toc']} mục" if info["toc"] else "Không có")]),
            ("Nội dung" + info["scope"], [
                ("Lớp chữ", info["text"]), ("Số ảnh", info["images"]),
                ("Ghi chú / tô sáng", info["annots"]), ("Liên kết", info["links"]),
                ("Ô biểu mẫu", info["widgets"]), ("File đính kèm", info["embedded"]),
                ("Phông chữ", info["fonts"])]),
            ("Bảo mật", [
                ("Mật khẩu mở file", yes(m.password)), ("Mã hoá", sec.get("method") or "Không"),
                ("In", perm("print")), ("Sao chép nội dung", perm("copy")), ("Chỉnh sửa", perm("modify")),
                ("Thêm ghi chú", perm("annotate")), ("Điền biểu mẫu", perm("form")),
                ("Chữ ký số", f"Có ({info['signatures']} chữ ký)" if info["signatures"] else "Không")]),
        ]
        parts = []
        for title, rows in sections:
            body = "".join(f"<tr><td style='color:#5f6368' width='190'>{escape(str(k))}</td><td>{v if k == 'Phông chữ' else escape(str(v))}</td></tr>"
                           for k, v in rows if v not in (None, ""))
            body = body or "<tr><td style='color:#80868b'>File không ghi thông tin này</td></tr>"
            parts.append(f"<h3 style='margin-bottom:2px'>{title}</h3><table cellpadding='3' width='100%'>{body}</table>")
        d = ReportDialog(self, "Thông tin tài liệu", "".join(parts))
        d.resize(700, 640)
        d.exec()

    # ---------------------------------------------------------------- trang
    def rotate(self, t, deg: int):
        pages = t.selected_pages()
        with t.model.edit(structure=True):
            for i in pages:
                p = t.model.doc[i]
                p.set_rotation((p.rotation + deg) % 360)

    def delete_pages(self, t):
        pages = t.selected_pages()
        if len(pages) >= t.model.page_count:
            return self.error("Không thể xoá hết mọi trang của tài liệu.")
        label = f"trang {pages[0] + 1}" if len(pages) == 1 else f"{len(pages)} trang đang chọn"
        if QMessageBox.question(self, APP_NAME, f"Xoá {label}?") != QMessageBox.Yes:
            return
        with t.model.edit(structure=True):
            t.model.doc.delete_pages(pages)

    def duplicate_page(self, t):
        i = t.viewer.current_page()
        with t.model.edit(structure=True):
            t.model.doc.fullcopy_page(i, i + 1 if i + 1 < t.model.page_count else -1)

    def move_page(self, t, d: int):
        i = t.viewer.current_page()
        j = i + d
        n = t.model.page_count
        if not 0 <= j < n:
            return
        order = list(range(n))
        order[i], order[j] = order[j], order[i]
        with t.model.edit(structure=True):
            t.model.doc.select(order)
        t.viewer.goto_page(j)

    def insert_blank(self, t):
        i = t.viewer.current_page()
        r = t.model.doc[i].rect
        with t.model.edit(structure=True):
            t.model.doc.new_page(pno=i + 1 if i + 1 < t.model.page_count else -1, width=r.width, height=r.height)
        t.viewer.goto_page(i + 1)

    def insert_file(self, t):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn file cần chèn", self.cfg.get("last_dir", ""), OPEN_FILTER)
        if not p:
            return
        self.busy()
        data, _eng = tools.any_to_pdf_bytes(p)
        try:
            src, _enc = tools.open_pdf_bytes(data)
        except PermissionError:
            self.done()
            pw, ok = QInputDialog.getText(self, "File có mật khẩu", "Nhập mật khẩu:", QLineEdit.Password)
            if not ok:
                return
            src, _enc = tools.open_pdf_bytes(data, pw)
        i = t.viewer.current_page()
        with t.model.edit(structure=True):
            t.model.doc.insert_pdf(src, start_at=i + 1 if i + 1 < t.model.page_count else -1)
        n = src.page_count
        src.close()
        self.done()
        self.msg(f"Đã chèn {n} trang")

    def merge(self):
        t = self.tab()
        pre = [t.model.path] if t and t.model.path and not t.model.dirty else []
        dlg = MergeDialog(self, self.cfg, OPEN_FILTER, pre)
        try:
            if not dlg.exec():
                return
            first = dlg.list.item(0).data(Qt.UserRole)
            prog, cb = self.progress("Đang gộp file…")
            try:
                data = dlg.result_bytes(cb)
            finally:
                prog.close()
            n_files = dlg.list.count()
        finally:
            dlg.close_docs()
        self.cfg["last_dir"] = os.path.dirname(first)   # hộp thoại Lưu sẽ mở sẵn ở thư mục của file đầu tiên
        self.cfg.save()
        m = DocModel(data, None, title="File gộp.pdf")
        m.has_sig = False
        self.add_tab(m)
        self.msg(f"Đã gộp {n_files} file thành {m.page_count} trang. Xem lại rồi bấm Lưu (Ctrl+S) để ghi file.")

    def split(self, t):
        base = Path(t.model.title).stem
        dlg = SplitDialog(self, t.model.doc, base, t.viewer.current_page(), self.cfg)
        sel = t.selected_pages()
        picking = t.side.isVisible() and t.side.currentWidget() is t.thumbs and t.active is t.own_viewer
        if len(sel) > 1 and picking:     # chỉ điền sẵn khi người dùng đang chủ động chọn NHIỀU trang ở tab Trang
            # đang chọn sẵn trang ở thanh bên: điền luôn để trích các trang đó ra MỘT file (thay cho mục "Trích trang" cũ)
            dlg.r_ranges.setChecked(True)
            dlg.e_ranges.setText(tools._pages_label(sorted(sel)))
        if not dlg.exec():
            return
        plan = dlg.plan
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu các file tách",
                                             os.path.dirname(t.model.path) if t.model.path else
                                             self.cfg.get("last_dir", ""))
        if not d:
            return
        names = tools.split_filenames(plan, base)
        clash = [n for n in names if os.path.exists(os.path.join(d, n))]
        if clash and QMessageBox.question(
                self, APP_NAME, f"Trong thư mục đã có {len(clash)} file trùng tên (ví dụ {clash[0]}).\nGhi đè lên?") \
                != QMessageBox.Yes:
            return
        prog, cb = self.progress("Đang tách file…")
        try:
            outs = tools.split_write(t.model.doc, plan, d, base, cb)
        finally:
            prog.close()
        self.cfg.save()
        if QMessageBox.question(self, APP_NAME, f"Đã tách thành {len(outs)} file trong thư mục:\n{d}\n\n"
                                "Mở thư mục này?") == QMessageBox.Yes:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(d))

    def page_numbers(self, t):
        o = form_dialog(self, "Đánh số trang", [
            ("fmt", "Mẫu", "choice", "{n} / {total}", [("{n} / {total}", "1 / 10"), ("{n}", "1"),
                                                       ("Trang {n}", "Trang 1"), ("Trang {n}/{total}", "Trang 1/10")]),
            ("pos", "Vị trí", "choice", "bottom-center", [("bottom-center", "Dưới, giữa"), ("bottom-right", "Dưới, phải"),
                                                          ("bottom-left", "Dưới, trái"), ("top-center", "Trên, giữa"),
                                                          ("top-right", "Trên, phải")]),
            ("size", "Cỡ chữ", "float", 10, (5, 40)), ("start", "Bắt đầu từ số", "int", 1, (0, 99999))])
        if o is None:
            return
        with t.model.edit(structure=True):
            tools.add_page_numbers(t.model.doc, o["fmt"], o["pos"], o["size"], o["start"])
            t.model.fonts_added = True

    def watermark(self, t):
        o = form_dialog(self, "Đóng dấu chìm", [
            ("text", "Nội dung", "str", "BẢN SAO"), ("size", "Cỡ chữ", "float", 60, (8, 300)),
            ("opacity", "Độ đậm (%)", "int", 18, (3, 100)), ("angle", "Góc nghiêng (độ)", "int", 45, (0, 90)),
            ("pages", "Trang áp dụng", "str", "", "Để trống = mọi trang. Ví dụ: 1-3, 5")])
        if o is None or not o["text"].strip():
            return
        pages = tools.parse_ranges(o["pages"], t.model.page_count)
        with t.model.edit(structure=True):
            tools.add_watermark(t.model.doc, o["text"], pages, o["size"], opacity=o["opacity"] / 100, angle=o["angle"])
            t.model.fonts_added = True

    def flatten(self, t):
        if QMessageBox.question(self, APP_NAME, "Gắn chết mọi ghi chú, chữ và ảnh đã thêm vào nội dung trang?\n"
                                "Sau đó không di chuyển hay xoá riêng từng cái được nữa.") != QMessageBox.Yes:
            return
        with t.model.edit(structure=True):
            t.model.doc.bake(annots=True, widgets=False)

    # ---------------------------------------------------------------- bookmark
    def side_toggle(self, t):
        t.side.setVisible(not t.side.isVisible())
        self._side_label()
        if t.side.isVisible():
            t.bookmarks.resync()        # mở lại thanh bên: bookmark phải khớp ngay với chỗ đang xem

    def _side_label(self):
        t = self.tab()
        text = "Ẩn thanh bên (trang, bookmark)" if t and t.side.isVisible() else "Hiện thanh bên (trang, bookmark)"
        self.a_side.setText(text)
        self.a_side.setToolTip(text + "  (F4)")

    def bookmark_show(self, t):
        t.side.setVisible(True)
        t.side.setCurrentWidget(t.bookmarks)
        self._side_label()

    def bookmark_add(self, t, child: bool):
        self.bookmark_show(t)
        t.bookmarks.add(child=child)
        self.msg("Đã thêm bookmark. Gõ tên rồi Enter. Bấm Lưu để ghi vào file.")

    def _bookmark_replace(self, t, toc: list, what: str):
        n = t.bookmarks.count()
        if n and QMessageBox.question(self, APP_NAME, f"Tài liệu đang có {n} bookmark. Thay toàn bộ bằng {what}?") \
                != QMessageBox.Yes:
            return
        with t.model.edit("toc"):
            t.model.doc.set_toc(toc)
        self.bookmark_show(t)
        self.msg(f"Đã tạo {len(toc)} bookmark. Bấm Lưu để ghi vào file.")

    def bookmark_auto(self, t):
        o = form_dialog(self, "Tự tạo bookmark từ các tiêu đề", [
            ("source", "Lấy tiêu đề từ", "choice", self.cfg.get("bm_source", "auto"), [
                ("auto", "Tự động (ưu tiên trang mục lục in sẵn)"),
                ("toc", "Trang mục lục in sẵn trong tài liệu"),
                ("font", "Kiểu chữ tiêu đề (chữ to hơn hoặc in đậm)")]),
            ("levels", "Số cấp tối đa", "int", int(self.cfg.get("bm_levels", 4)), (1, 8))],
            note="Bookmark được dựng nhiều cấp lồng nhau (cấp 1, 2, 3…). Tạo xong vẫn chỉnh tay được.",
            ok_text="Tạo bookmark")
        if o is None:
            return
        self.cfg["bm_source"], self.cfg["bm_levels"] = o["source"], o["levels"]
        self.busy()
        try:
            toc, how = tools.guess_headings(t.model.doc, o["levels"], o["source"])
        finally:
            self.done()
        if not toc:
            hint = {"toc": "Không tìm thấy trang mục lục in sẵn (dạng “Tiêu đề ....... số trang”) trong 40 trang đầu, "
                           "hoặc không dò được trang đích.\nThử chọn “Kiểu chữ tiêu đề”.",
                    "font": "Không nhận ra tiêu đề nào theo kiểu chữ (tài liệu cần có lớp chữ; tiêu đề phải to hơn "
                            "hoặc đậm hơn chữ nội dung)."}.get(o["source"],
                   "Không nhận ra tiêu đề nào (tài liệu cần có lớp chữ; bản scan phải OCR trước).")
            return self.info(hint + "\nBro có thể thêm tay bằng Ctrl+B.")
        depth = max(x[0] for x in toc)
        self._bookmark_replace(t, toc, f"{len(toc)} bookmark ({depth} cấp) lấy từ {how}")

    def bookmark_pages(self, t):
        toc = [[1, f"Trang {i + 1}", i + 1] for i in range(t.model.page_count)]
        self._bookmark_replace(t, toc, "bookmark cho từng trang")

    def bookmark_clear(self, t):
        n = t.bookmarks.count()
        if not n:
            return self.info("Tài liệu chưa có bookmark nào.")
        if QMessageBox.question(self, APP_NAME, f"Xoá cả {n} bookmark của tài liệu?") == QMessageBox.Yes:
            t.bookmarks.clear_all()

    # ---------------------------------------------------------------- chuyển đổi
    def to_word(self, t):
        out = self._out_path(t, "", ".docx", "Word (*.docx)")
        if not out:
            return
        self.msg("Đang chuyển sang Word, tài liệu dài có thể mất vài phút…", 0)
        self.busy()
        tmp = self._temp_pdf(t)
        try:
            tools.pdf_to_docx(tmp, out)
        finally:
            os.unlink(tmp)
            self.done()
        self.msg(f"Đã xuất: {out}")
        self.info(f"Đã chuyển sang Word:\n{out}\n\nLưu ý: bố cục phức tạp có thể lệch so với bản PDF, "
                  "bản scan cần chạy OCR trước.")

    def to_excel(self, t):
        out = self._out_path(t, "", ".xlsx", "Excel (*.xlsx)")
        if not out:
            return
        self.busy()
        n = tools.pdf_to_xlsx(t.model.doc, out)
        self.done()
        self.info(f"Đã xuất: {out}\n" + (f"Tìm thấy {n} bảng." if n else
                                         "Không nhận ra bảng nào, nội dung được ghi theo từng dòng chữ."))

    def to_images(self, t):
        o = form_dialog(self, "PDF → Ảnh", [
            ("fmt", "Định dạng", "choice", "png", [("png", "PNG (nét, file lớn)"), ("jpg", "JPG (file nhỏ)")]),
            ("dpi", "Độ phân giải (DPI)", "int", 150, (50, 600)),
            ("pages", "Trang", "str", "", "Để trống = mọi trang. Ví dụ: 1-3, 5")], ok_text="Chọn thư mục lưu…")
        if o is None:
            return
        pages = tools.parse_ranges(o["pages"], t.model.page_count)
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu ảnh",
                                             os.path.dirname(t.model.path) if t.model.path else "")
        if not d:
            return
        prog, cb = self.progress("Đang xuất ảnh…")
        try:
            outs = tools.pdf_to_images(t.model.doc, d, Path(t.model.title).stem, o["fmt"], o["dpi"], pages, cb)
        finally:
            prog.close()
        self.info(f"Đã xuất {len(outs)} ảnh vào:\n{d}")

    def translate_doc(self, t):
        from . import translate as T
        from .dialogs import TranslateDialog
        m = t.model
        dlg = TranslateDialog(self, self.cfg, m.page_count, t.viewer.current_page())
        if not dlg.exec():
            return
        self.cfg.save()
        o = dlg.options()
        pages = tools.parse_ranges(o["pages"], m.page_count)
        from . import tm
        from .dialogs import data_dir
        mem = tm.memory(data_dir())
        code = T.lang_name(o["target"])[0]
        from . import ocr
        kind = o.get("images", "off")
        img_note = ""
        if kind == "auto":         # chữ trong hình: mặc định dùng cùng nơi với bộ máy dịch, không tự ý gửi ảnh đi chỗ khác
            kind = "gemini" if o["engine"] == "gemini" and self.cfg.get("gemini_key") else \
                "rapid" if ocr.rapid_available() else "tesseract" if tools.tess_languages() else "off"
            if kind == "off":
                img_note = ("Chữ nằm trong hình ảnh chưa được dịch vì máy chưa có bộ máy nhận dạng chữ nào (dùng Gemini, "
                            "hoặc cài RapidOCR trong hộp Nhận dạng chữ).")
        elif kind == "rapid" and not ocr.rapid_available():
            return self.error("RapidOCR chưa được cài. Mở Chuyển đổi → Nhận dạng chữ (OCR), chọn RapidOCR và bấm nút cài, "
                              "hoặc chọn bộ máy khác cho chữ trong hình ảnh.")
        elif kind == "tesseract" and not tools.tess_languages():
            return self._tesseract_help()
        ocr_engine = None
        data = m.doc.tobytes()
        work = pymupdf.open(stream=data, filetype="pdf")   # làm trên bản sao, file gốc không bị đụng tới
        if kind == "off":
            self.busy()
            try:
                job = T.collect(work, pages, with_toc=o["toc"])
            finally:
                self.done()
        else:
            prog = QProgressDialog("Đang đọc chữ trong các hình ảnh…", "Dừng", 0, len(pages), self)
            prog.setWindowTitle(APP_NAME)
            prog.setWindowModality(Qt.WindowModal)
            prog.setMinimumDuration(0)
            prog.setAutoClose(False)
            prog.setAutoReset(False)
            prog.setValue(0)
            stop = {"on": False}

            def cancel():
                stop["on"] = True
                if ocr_engine is not None:
                    ocr_engine.cancel = True
            prog.canceled.connect(cancel)

            def on_page(a, b):
                if stop["on"]:
                    raise T.Cancelled()
                prog.setValue(a)
                prog.setLabelText(f"Đang đọc chữ trong các hình ảnh… trang {a}/{b}")
                QApplication.processEvents()
            try:
                opts = {"model_dir": "", "lang": "latin"}
                if kind == "gemini":
                    ocr_engine = T.make_engine("gemini", self.cfg)
                    opts["gemini"] = ocr_engine
                elif kind == "tesseract":
                    langs = tools.tess_languages()
                    opts["lang"] = "vie+eng" if "vie" in langs and "eng" in langs else langs[0]
                elif (o.get("source") or "") not in ("", "vi", "fr", "de", "es", "pt", "it"):
                    opts["lang"] = "multi"
                reader = ocr.make_reader(kind, opts, self.offload, lambda s_: prog.setLabelText(s_), min_score=0.6)
                job = T.collect(work, pages, with_toc=o["toc"], image_reader=reader, progress=on_page,
                                store=mem if o.get("tm", True) else None)
            except T.Cancelled:
                work.close()
                prog.close()
                return self.msg("Đã dừng dịch.")
            except (ocr.OcrError, T.TranslateError) as e:
                prog.close()
                if QMessageBox.question(self, APP_NAME, "Không đọc được chữ trong hình ảnh:\n\n" + str(e)[:600]
                                        + "\n\nVẫn dịch phần chữ thường (bỏ qua chữ trong hình)?") != QMessageBox.Yes:
                    work.close()
                    return
                img_note = "Chữ nằm trong hình ảnh chưa được dịch (bộ máy nhận dạng chữ báo lỗi)."
                if ocr_engine is not None:
                    ocr_engine.cancel = False
                job = T.collect(work, pages, with_toc=o["toc"])
            finally:
                prog.canceled.disconnect(cancel)     # đóng hộp tiến độ cũng phát tín hiệu "Dừng": không để nó huỷ bước dịch
                prog.close()
            if ocr_engine is not None:
                ocr_engine.cancel = False
        job["img_note"] = img_note
        if kind == "gemini":
            try:        # lưu câu trả lời gần nhất của Gemini khi đọc hình, để tra lại nếu đọc thiếu
                with open(os.path.join(data_dir(), "ocr_gemini_gan_nhat.txt"), "w", encoding="utf-8") as f:
                    f.write(ocr.last_raw.get("text", ""))
            except Exception:
                pass
        if not job["texts"] and kind != "off":
            work.close()
            rot = any(m.doc[i].rotation for i in pages)
            return self.info(f"Không có chữ nào để dịch: đã đọc {job['img_seen']} hình/trang ảnh bằng bộ máy nhận dạng, "
                             f"nhận được {job['img_lines']} dòng chữ."
                             + ("\n\nTrang đang bị xoay: hãy xoay trang về đúng chiều (menu Trang) rồi dịch lại."
                                if rot and not job["img_seen"] else "")
                             + ("\n\nBộ máy nhận dạng không trả về dòng nào. Thử lại, hoặc đổi ô “Đọc chữ trong hình” sang "
                                "bộ máy khác." if job["img_seen"] and not job["img_lines"] else ""))
        if not job["texts"]:
            work.close()
            return self.info("Không tìm thấy chữ nào để dịch trong các trang đã chọn.\n"
                             "Nếu đây là bản scan hoặc ảnh chụp (chữ nằm trong ảnh), hãy tích ô "
                             "“Dịch cả chữ nằm trong hình ảnh” trong hộp dịch rồi dịch lại.")
        o["context"] = job["context"]
        texts = job["texts"]
        result: list = [None] * len(texts)
        if o.get("tm", True):                      # câu đã dịch lần trước: lấy lại ngay từ bộ nhớ dịch
            try:
                result = mem.lookup(code, texts)
            except Exception:
                pass
        miss = [k for k, r in enumerate(result) if r is None]
        from_mem = len(texts) - len(miss)
        engine = None
        if miss:
            try:
                engine = ocr_engine if o["engine"] == "gemini" and ocr_engine is not None else \
                    T.make_engine(o["engine"], self.cfg)
            except Exception:
                work.close()
                raise
            ocr_name = {"gemini": "Gemini", "rapid": "RapidOCR", "tesseract": "Tesseract"}.get(kind, "")
            head = f"Đã đọc xong chữ trong hình bằng {ocr_name}.\n" if ocr_name else ""
            if not self._run_engine(engine, [texts[k] for k in miss], o, from_mem, result, miss, head):
                work.close()
                return
            try:
                mem.store(code, [(texts[k], result[k]) for k in miss])
            except Exception:
                pass
        self._finish_translation(t, m, work, job, result, o, engine, code, from_mem, len(miss))

    def _run_engine(self, engine, texts, o, from_mem, result, miss, head="") -> bool:
        prog = QProgressDialog(f"{head}Đang dịch bằng {engine.name}…", "Dừng", 0, 100, self)
        prog.setWindowTitle(APP_NAME)
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)
        prog.setAutoClose(False)
        prog.setAutoReset(False)
        prog.setValue(0)
        worker = TranslateWorker(engine, texts, o)
        extra = f" (đã lấy sẵn {from_mem} đoạn từ bộ nhớ dịch)" if from_mem else ""

        def on_progress(a, b, note):
            if note:
                prog.setLabelText(f"{head}Bước dịch bằng {engine.name}: {note}")
            elif b > 0:
                prog.setMaximum(b)
                prog.setValue(a)
                prog.setLabelText(f"{head}Đang dịch bằng {engine.name}… {a}/{b} đoạn{extra}")
        worker.progress.connect(on_progress)
        prog.canceled.connect(lambda: setattr(engine, "cancel", True))
        loop = QEventLoop()
        worker.finished.connect(loop.quit)
        worker.start()
        loop.exec()
        prog.close()
        if worker.cancelled:
            self.msg("Đã dừng dịch.")
            return False
        if worker.error or worker.result is None:
            self.error("Không dịch được.\n\n" + (worker.error or "Bộ máy dịch không trả kết quả."))
            return False
        for k, r in zip(miss, worker.result):
            result[k] = r
        return True

    def _finish_translation(self, t, m, work, job, result, o, engine, code, from_mem, n_new):
        from . import translate as T
        src_bytes = None
        prog2, cb = self.progress("Đang ghép bản dịch vào trang…")
        try:
            src_bytes = m.doc.tobytes()
            stats = T.apply(work, job, result, cb)
            out = work.tobytes(garbage=3, deflate=True)
        finally:
            prog2.close()
            work.close()
        if engine is not None and o["engine"] == "gemini" and getattr(engine, "model", "") and not self.cfg.get("gemini_model"):
            self.cfg["gemini_prefer"] = engine.model     # lần sau dùng luôn model đã chạy được, khỏi dò lại
            self.cfg.save()
        nm = DocModel(out, None, title=f"{Path(m.title).stem}_{code}.pdf")
        nm.has_sig = False
        self.cfg["last_dir"] = os.path.dirname(m.path) if m.path else self.cfg.get("last_dir", "")
        nt = self.add_tab(nm)
        src_tab = t if t.active is t.own_viewer else t.partner_tab   # tab chứa tài liệu vừa được dịch
        nt.source_tab = src_tab
        # giữ lại bản gốc + từng cặp câu để rà soát/sửa câu dịch theo trang (Chuyển đổi → Rà soát câu dịch)
        nt.tr_state = {"src": src_bytes, "target": code, "n": m.page_count,
                 "pages": {i: [(u["text"], result[start + k] or u["text"]) for k, u in enumerate(units)]
                           for i, units, start in job["pages"]},
                 "units": {i: units for i, units, start in job["pages"]}}
        used = sorted(getattr(engine, "used", []) or [])
        how = (f"bằng {engine.name}" + (f" (model {', '.join(used)})" if used else "")) if engine is not None \
            else "hoàn toàn từ bộ nhớ dịch, không gọi máy dịch"
        lines = [f"Đã dịch {stats['replaced']} / {stats['units']} đoạn chữ {how}.",
                 "Bản dịch đang mở ở tab mới và chưa được lưu: xem lại rồi bấm Lưu (Ctrl+S)."]
        if from_mem and engine is not None:
            lines.insert(1, f"{from_mem} đoạn lấy lại từ bộ nhớ dịch, {n_new} đoạn mới gọi máy dịch.")
        lines.insert(2 if from_mem and engine is not None else 1,
                     "Muốn sửa câu dịch cho chuẩn: Chuyển đổi → Rà soát / sửa câu dịch của trang này (Ctrl+Alt+G).")
        if job.get("img_units"):
            lines.append(f"Trong đó có {job['img_units']} dòng chữ nằm trong hình ảnh (đã nhận dạng rồi dịch đè lên hình). "
                         "Chữ quá mờ hoặc quá nhỏ thì được giữ nguyên.")
        if job.get("img_note"):
            lines.append(job["img_note"])
        if stats["no_text"]:
            lines.append(f"{len(stats['no_text'])} trang là ảnh/bản scan nên chưa được dịch (muốn dịch, hãy tích ô "
                         "“Dịch cả chữ nằm trong hình ảnh” trong hộp dịch): trang "
                         + ", ".join(str(p + 1) for p in stats["no_text"][:15]) + ("…" if len(stats["no_text"]) > 15 else ""))
        if stats["skipped_rot"]:
            lines.append(f"{stats['skipped_rot']} dòng chữ xoay nghiêng được giữ nguyên, chưa dịch.")
        if getattr(m, "has_sig", False):
            lines.append("File gốc có chữ ký số; bản dịch là file mới nên không còn chữ ký đó.")
        lines.append("Máy dịch có thể sai thuật ngữ hoặc ngữ cảnh: với hợp đồng và văn bản pháp lý nên có người rà lại.")
        box = QMessageBox(QMessageBox.Information, APP_NAME, "\n\n".join(lines), parent=self)
        b_cmp = box.addButton("So sánh song song gốc – dịch", QMessageBox.AcceptRole)
        box.addButton("Đóng", QMessageBox.RejectRole)
        box.setDefaultButton(b_cmp)
        box.exec()
        if box.clickedButton() is b_cmp:
            self.start_compare(nt, src_tab)

    def _review_tab(self, t) -> DocTab | None:
        """Tab bản dịch dùng được bảng rà soát: chính tab này, hoặc tab bản dịch tạo ra từ tab này (lấy cái mới nhất)."""
        if t is None:
            return None
        if t.tr_state:
            return t
        for x in reversed(self.doc_tabs()):
            if x.source_tab is t and x.tr_state:
                return x
        return None

    def review_translation(self, t):
        """Bảng câu gốc – câu dịch của trang đang xem; sửa xong thì dựng lại trang từ bản gốc và lưu vào bộ nhớ dịch."""
        from . import tm
        from . import translate as T
        from .dialogs import ReviewDialog, data_dir
        target = self._review_tab(t)
        if target is not None and target is not t:      # đang đứng ở bản gốc: chuyển sang tab bản dịch, đúng trang đang xem
            page = t.viewer.current_page()
            self.tabs.setCurrentWidget(target)
            target.goto_both(page)
            t = target
        if t.partner is not None:
            t.set_active(t.own_viewer)
        st = getattr(t, "tr_state", None)
        m = t.own_model
        if not st:
            return self.info("Bảng rà soát chỉ dùng được trên tab bản dịch vừa tạo trong phiên này.\n\n"
                             "Với bản dịch đã lưu từ trước: mở lại file GỐC rồi chạy Dịch tài liệu. Các câu đã dịch được lấy "
                             "ngay từ bộ nhớ dịch (không phải chờ), sau đó dùng bảng rà soát trên tab bản dịch mới.")
        if m.page_count != st["n"]:
            return self.info("Bản dịch đã bị thêm/xoá/đổi thứ tự trang nên không còn khớp với bản gốc để dựng lại trang.")
        i = t.own_viewer.current_page()
        pairs = st["pages"].get(i)
        if not pairs:
            return self.info(f"Trang {i + 1} không có đoạn chữ nào đã dịch.")
        dlg = ReviewDialog(self, i + 1, pairs)
        if not dlg.exec():
            return
        rows = dlg.changed_rows()
        if not rows:
            return self.msg("Không có câu nào thay đổi.")
        new = dlg.result_texts()
        src = pymupdf.open(stream=st["src"], filetype="pdf")
        try:
            units = st["units"].get(i) or []      # dùng lại đúng các đoạn của lần dịch (kể cả chữ đã đọc trong hình ảnh)
            if [u["text"] for u in units] != [s for s, _d in pairs]:
                return self.error("Không dựng lại được trang này từ bản gốc.")
            T.apply_page(src[i], units, new)
            tools.finalize_fonts(src)
            with m.edit(structure=True):
                toc = m.doc.get_toc(simple=False)
                m.doc.insert_pdf(src, from_page=i, to_page=i, start_at=i)
                m.doc.delete_page(i + 1)
                if toc:
                    m.doc.set_toc([[lv, title, pg, {a: b for a, b in (dest or {}).items() if a != "xref"}]
                                   for lv, title, pg, dest in toc])
        finally:
            src.close()
        st["pages"][i] = [(s, new[k]) for k, (s, _d) in enumerate(pairs)]
        if dlg.save_tm.isChecked():
            try:
                tm.memory(data_dir()).store(st["target"], [(pairs[r][0], new[r]) for r in rows], origin="manual")
            except Exception:
                pass
        t.own_viewer.goto_page(i)
        self.msg(f"Đã sửa {len(rows)} câu ở trang {i + 1}" + (" và lưu vào bộ nhớ dịch." if dlg.save_tm.isChecked() else "."))

    def export_images(self, t):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu hình ảnh",
                                             os.path.dirname(t.model.path) if t.model.path else "")
        if not d:
            return
        prog, cb = self.progress("Đang xuất hình ảnh…")
        try:
            n = tools.export_all_images(t.model.doc, d, Path(t.model.title).stem, progress=cb)
        finally:
            prog.close()
        self.info(f"Đã xuất {n} hình ảnh vào:\n{d}" if n else "Tài liệu không có hình ảnh nào để xuất.")

    def to_text(self, t):
        out = self._out_path(t, "", ".txt", "Văn bản (*.txt)")
        if out:
            tools.pdf_to_text(t.model.doc, out)
            self.msg(f"Đã xuất: {out}")

    def to_html(self, t):
        out = self._out_path(t, "", ".html", "HTML (*.html)")
        if out:
            tools.pdf_to_html(t.model.doc, out)
            self.msg(f"Đã xuất: {out}")

    def offload(self, fn):
        """Chạy fn ở luồng phụ (chờ mạng / tính toán nặng) trong khi cửa sổ vẫn phản hồi; trả kết quả hoặc ném lại lỗi.
        fn không được đụng tới PyMuPDF (thư viện này chỉ an toàn ở luồng chính)."""
        box = {}

        class Job(QThread):
            def run(self):
                try:
                    box["res"] = fn()
                except BaseException as e:      # kể cả Cancelled
                    box["err"] = e
        job = Job()
        loop = QEventLoop()
        job.finished.connect(loop.quit)
        job.start()
        loop.exec()
        job.wait()
        if "err" in box:
            raise box["err"]
        return box.get("res")

    def _tesseract_help(self):
        win = sys.platform.startswith("win")
        steps = ("1. Tải bộ cài “tesseract-ocr-w64-setup” (bản của UB Mannheim, miễn phí).\n"
                 "2. Khi cài, ở bước chọn thành phần mở mục “Additional language data” và tick “Vietnamese”.\n"
                 "3. Giữ nguyên thư mục cài mặc định (C:\\Program Files\\Tesseract-OCR).\n"
                 "4. Đóng PDF Editor Lite rồi mở lại.") if win else \
                ("Linux Mint: sudo apt install tesseract-ocr tesseract-ocr-vie\n"
                 "macOS: brew install tesseract tesseract-lang\nSau đó mở lại PDF Editor Lite.")
        self.error("Bộ máy Tesseract chưa được cài trên máy này.\n\n"
                   "OCR chỉ cần cho bản scan hoặc ảnh chụp (trang không chọn được chữ). "
                   "File đã chọn và tìm kiếm được chữ thì không cần OCR.\n\nCách cài:\n" + steps
                   + "\n\nHoặc chọn bộ máy RapidOCR / Gemini trong hộp Nhận dạng chữ.")

    def install_rapidocr(self) -> bool:
        """Cài RapidOCR vào đúng môi trường Python của app (làm một lần, cần mạng)."""
        import importlib
        import subprocess
        from . import ocr
        if tools.FROZEN:
            self.info("Bản cài đặt này chưa có thành phần RapidOCR.\n\nChạy lại bộ cài PDF Editor Lite, ở bước chọn thành phần "
                      "hãy tích “OCR trên máy cho ảnh chụp / scan xấu (RapidOCR)”.")
            return False
        cmd = [sys.executable.replace("pythonw.exe", "python.exe"), "-m", "pip", "install", "rapidocr", "onnxruntime"]
        box = {"rc": None, "out": ""}

        class Job(QThread):
            def run(self):
                try:
                    flags = 0x08000000 if sys.platform.startswith("win") else 0      # không bật cửa sổ đen
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, creationflags=flags)
                    box["rc"], box["out"] = r.returncode, (r.stdout or "")[-600:] + (r.stderr or "")[-900:]
                except Exception as e:
                    box["rc"], box["out"] = 1, str(e)
        job = Job()
        prog = QProgressDialog("Đang tải và cài RapidOCR (khoảng 100 MB), vui lòng chờ…", None, 0, 0, self)
        prog.setWindowTitle(APP_NAME)
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)
        prog.show()
        loop = QEventLoop()
        job.finished.connect(loop.quit)
        job.start()
        loop.exec()
        prog.close()
        importlib.invalidate_caches()
        if box["rc"] == 0 and ocr.rapid_available():
            self.info("Đã cài xong RapidOCR.")
            return True
        self.error("Chưa cài được RapidOCR. Kiểm tra mạng rồi thử lại.\n\n" + box["out"][-900:])
        return False

    def ocr(self, t):
        from . import ocr
        from . import translate as T
        from .dialogs import OcrDialog, data_dir
        m = t.model
        doc = m.doc
        dlg = OcrDialog(self, self.cfg, tools.tess_languages(), ocr.rapid_available(), self.install_rapidocr)
        if not dlg.exec():
            return
        self.cfg.save()
        o = dlg.options()
        if o["engine"] == "tesseract" and not tools.tess_languages():
            return self._tesseract_help()
        sample = range(min(doc.page_count, 30))
        with_text = sum(1 for i in sample if ocr.has_text(doc[i]))
        if o["only_scans"] and sample and with_text == doc.page_count:
            return self.info("Mọi trang của tài liệu này đã có sẵn lớp chữ (chọn và tìm kiếm được), không cần OCR.\n"
                             "Nếu vẫn muốn nhận dạng lại, bỏ tích “Chỉ nhận dạng các trang chưa có chữ”.")
        if not o["only_scans"] and sample and with_text >= len(sample) * 0.8:
            if QMessageBox.question(self, APP_NAME, "Tài liệu này đã có sẵn lớp chữ (chọn và tìm kiếm được), không cần OCR.\n"
                                    "Nếu vẫn chạy, chữ nhận dạng sẽ chồng thêm lên (hoặc trang bị đổi thành ảnh với "
                                    "Tesseract).\n\nVẫn chạy OCR?") != QMessageBox.Yes:
                return
        engine = None
        o["model_dir"] = os.path.join(data_dir(), "ocr_models")
        if o["engine"] == "gemini":
            engine = T.make_engine("gemini", self.cfg)
            o["gemini"] = engine
        data = doc.tobytes()
        names = {"tesseract": "Tesseract", "rapid": "RapidOCR", "gemini": "Gemini"}
        prog = QProgressDialog(f"Đang nhận dạng chữ bằng {names[o['engine']]}…", "Dừng", 0, doc.page_count, self)
        prog.setWindowTitle(APP_NAME)
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)
        prog.setAutoClose(False)
        prog.setAutoReset(False)
        prog.setValue(0)
        box = {"stop": False, "res": None, "err": "", "cancelled": False}

        def on_progress(a, b):
            prog.setMaximum(b)
            prog.setValue(a)
            prog.setLabelText(f"Đang nhận dạng chữ bằng {names[o['engine']]}… trang {a}/{b}")
            QApplication.processEvents()

        def stop():
            box["stop"] = True
            if engine is not None:
                engine.cancel = True
        prog.canceled.connect(stop)
        try:
            box["res"] = ocr.run(data, o["engine"], o, progress=on_progress, note=lambda s_: prog.setLabelText(s_),
                                 cancel=lambda: box["stop"], offload=self.offload)
        except T.Cancelled:
            box["cancelled"] = True
        except (ocr.OcrError, T.TranslateError, tools.PdfError) as e:
            box["err"] = str(e)
        finally:
            prog.close()
        if box["cancelled"]:
            return self.msg("Đã dừng nhận dạng chữ.")
        if box["err"] or box["res"] is None:
            return self.error("Không nhận dạng được.\n\n" + (box["err"] or "Bộ máy OCR không trả kết quả."))
        out, st = box["res"]
        if t.partner is not None and t.model is not m:
            t.set_active(t.own_viewer)
        m.replace_document(out)
        count = f" ({st['lines']} dòng chữ)" if o["engine"] != "tesseract" else ""
        lines = [f"Đã nhận dạng {st['pages']} trang bằng {names[o['engine']]}{count}. Giờ có thể tìm kiếm, chọn và sao chép "
                 "chữ; bấm Lưu để ghi file."]
        if o["engine"] == "gemini":
            try:        # lưu câu trả lời gần nhất của Gemini để tra lại khi nhận dạng thiếu dòng
                with open(os.path.join(data_dir(), "ocr_gemini_gan_nhat.txt"), "w", encoding="utf-8") as f:
                    f.write(ocr.last_raw.get("text", ""))
            except Exception:
                pass
        if st.get("read", 0) > st["lines"]:
            lines.append(f"{st['read'] - st['lines']} dòng đọc được nhưng không đặt được vào trang.")
        if st["skipped"]:
            lines.append(f"{st['skipped']} trang đã có sẵn chữ nên được giữ nguyên.")
        if st["empty"]:
            lines.append("Không đọc được chữ nào ở trang: " + ", ".join(str(i + 1) for i in st["empty"][:20])
                         + ("…" if len(st["empty"]) > 20 else "") + " (trang trắng hoặc toàn hình).")
        if o["engine"] == "gemini":
            lines.append("Gemini có thể đoán sai chữ nhìn không rõ: nên rà lại con số, tên riêng quan trọng.")
        self.info("\n\n".join(lines))

    def compress(self, t):
        o = form_dialog(self, "Nén giảm dung lượng", [
            ("level", "Mức nén", "choice", "medium", [("low", "Nhẹ (giữ nguyên ảnh)"), ("medium", "Vừa (ảnh 150 DPI)"),
                                                      ("high", "Mạnh (ảnh 96 DPI, file nhỏ nhất)")])])
        if o is None:
            return
        self.busy()
        before = len(t.model.doc.tobytes(garbage=3, deflate=True))
        data = tools.compress_bytes(t.model.doc, o["level"])
        self.done()
        if len(data) >= before * 0.98:
            return self.info(f"File đã gọn sẵn ({before / 1024 / 1024:.2f} MB), nén thêm không giảm đáng kể.")
        t.model.replace_document(data)
        self.info(f"Dung lượng: {before / 1024 / 1024:.2f} MB → {len(data) / 1024 / 1024:.2f} MB "
                  f"(giảm {100 - len(data) * 100 // before}%).\nBấm Lưu để ghi file.")

    # ---------------------------------------------------------------- ký & bảo mật
    def hand_signature(self, t):
        d = SignatureLibrary(self)
        if d.exec() and d.selected():
            t.viewer.set_tool("image", d.selected())
            t.viewer.setFocus()

    def do_sign(self, t: DocTab, page, rect):
        from . import signing
        m = t.model
        if m.password:
            return self.error("File đang có mật khẩu. Hãy gỡ mật khẩu (Ký & Bảo mật → Gỡ mật khẩu) và lưu lại trước khi ký số.")
        if getattr(m, "has_sig", False) and m.dirty:
            r = QMessageBox.warning(self, APP_NAME, "Tài liệu đã có chữ ký số và bạn vừa chỉnh sửa nó.\nNếu ký tiếp, chữ ký "
                                    "cũ sẽ mất hiệu lực.\n\nMuốn ký thêm mà vẫn giữ chữ ký cũ: hãy mở lại file gốc và ký "
                                    "ngay, không sửa gì.\n\nVẫn tiếp tục?", QMessageBox.Yes | QMessageBox.No)
            if r != QMessageBox.Yes:
                return
        self.busy()
        data = m.export_bytes()
        empty = signing.empty_signature_fields(data)
        self.done()
        dlg = SignDialog(self, self.cfg, rect is not None, empty)
        try:
            if not dlg.exec():
                return
            existing = dlg.field.currentData() or None
            box = appearance = None
            if existing:
                appearance = signing.make_appearance(220, 80, dlg.lines(), dlg.img.currentData() or None)
            elif rect is not None:
                box = signing.pdf_box(m.doc[page], rect)
                appearance = signing.make_appearance(rect.width, rect.height, dlg.lines(), dlg.img.currentData() or None)
            out = self._out_path(t, "_da_ky", ".pdf", "PDF (*.pdf)")
            if not out:
                return
            self.busy()
            signed = signing.sign_pdf(data, dlg.signer, page_index=page, box=box, appearance=appearance,
                                      existing_field=existing, reason=dlg.reason.text().strip(),
                                      location=dlg.location.text().strip(), tsa_url=dlg.tsa.text().strip(),
                                      certify=dlg.certify.isChecked())
            Path(out).write_bytes(signed)
        except signing.SignError as e:
            self.done()
            return self.error(str(e))
        finally:
            self.done()
            dlg.close_session()
        same = m.path and os.path.normcase(os.path.abspath(out)) == os.path.normcase(m.path)
        if same or not m.dirty:
            self.close_tab(self.tabs.indexOf(t), force=True)
        nt = self.open_path(out)
        if nt:
            nt.viewer.goto_page(page or 0)
        self.info(f"Đã ký số thành công.\n\nFile đã ký: {out}\n\nLưu ý: đừng chỉnh sửa hay lưu đè file này nữa, "
                  "vì mọi thay đổi sẽ làm chữ ký mất hiệu lực.")

    def verify(self, t):
        from . import signing
        m = t.model
        data = m.base_data if (m.base_data and not m.password) else m.export_bytes()
        self.busy()
        res = signing.verify_signatures(data, trust_dir())
        self.done()
        if not res:
            return self.info("Tài liệu này không có chữ ký số nào.")
        parts = []
        if m.dirty:
            parts.append("<p style='color:#b06000'>Bạn đang có chỉnh sửa chưa lưu. Kết quả dưới đây là của bản đang nằm "
                         "trên đĩa.</p>")
        for k, r in enumerate(res, 1):
            i = r["info"]
            if r["error"]:
                head = "<span style='color:#d93025'>✘ Không kiểm tra được</span>"
            elif r["ok"]:
                head = "<span style='color:#188038'>✔ Chữ ký hợp lệ, nội dung không bị sửa sau khi ký</span>"
            else:
                head = "<span style='color:#d93025'>✘ KHÔNG HỢP LỆ: nội dung đã bị thay đổi sau khi ký</span>"
            trust = ("<span style='color:#188038'>Chứng thư thuộc chuỗi tin cậy</span>" if r["trusted"] else
                     "<span style='color:#b06000'>Chưa xác nhận được nhà cung cấp (chưa có chứng thư gốc tin cậy, "
                     "xem ghi chú bên dưới)</span>")
            tm = r["time"].astimezone().strftime("%d/%m/%Y %H:%M:%S") if r["time"] else "không rõ"
            rows = [("Người ký", i.get("cn", "?")), ("Đơn vị", i.get("org", "")), ("Cấp bởi", i.get("issuer", "")),
                    ("Số serial", i.get("serial", "")),
                    ("Hiệu lực chứng thư", f"{i['not_before']:%d/%m/%Y} – {i['not_after']:%d/%m/%Y}" if i else ""),
                    ("Thời điểm ký", tm + (" (có dấu thời gian TSA)" if r["tsa"] else " (theo đồng hồ máy người ký)")),
                    ("Lý do", r["reason"]), ("Nơi ký", r["location"]), ("Sau khi ký", r["modified"]),
                    ("Nguồn gốc", trust), ("Lỗi", r["error"])]
            body = "".join(f"<tr><td style='color:#5f6368'>{a}</td><td>{b}</td></tr>" for a, b in rows if b)
            parts.append(f"<h3>Chữ ký {k}: {head}</h3><table cellpadding='3'>{body}</table>")
        parts.append("<hr><p style='color:#5f6368'>Ghi chú: PDF Editor Lite kiểm tra được tính toàn vẹn (file có bị sửa sau khi ký "
                     "hay không). Để xác nhận cả nhà cung cấp chữ ký số, hãy chép chứng thư gốc (.cer) của nhà cung cấp "
                     "và của Root CA Quốc gia vào thư mục chứng thư tin cậy (Ký &amp; Bảo mật → Mở thư mục chứng thư "
                     "gốc tin cậy). Việc kiểm tra thu hồi chứng thư trực tuyến chưa được hỗ trợ.</p>")
        ReportDialog(self, "Kết quả kiểm tra chữ ký số", "".join(parts)).exec()

    def set_password(self, t):
        o = form_dialog(self, "Đặt mật khẩu cho file", [
            ("pw", "Mật khẩu mở file", "password", ""), ("pw2", "Nhập lại", "password", ""),
            ("print", "Cho phép in", "bool", True), ("copy", "Cho phép sao chép chữ", "bool", True)],
            note="File có mật khẩu sẽ được lưu thành một bản mới (mã hoá AES-256).")
        if o is None:
            return
        if not o["pw"] or o["pw"] != o["pw2"]:
            return self.error("Mật khẩu trống hoặc hai lần nhập không khớp.")
        out = self._out_path(t, "_bao_mat", ".pdf", "PDF (*.pdf)")
        if not out:
            return
        if t.model.fonts_added:
            tools.finalize_fonts(t.model.doc)
        tools.save_encrypted(t.model.doc, out, o["pw"], allow_print=o["print"], allow_copy=o["copy"])
        self.info(f"Đã lưu bản có mật khẩu:\n{out}")

    def remove_password(self, t):
        m = t.model
        if not m.password:
            return self.info("File này không có mật khẩu mở.")
        m.password = None
        m.encrypted = False
        m.dirty = True
        m.stateChanged.emit()
        self.info("Đã gỡ mật khẩu. Bấm Lưu (hoặc Lưu thành…) để ghi file không còn mật khẩu.")

    def open_trust_dir(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(trust_dir()))

    def about(self):
        so = tools.find_soffice()
        ocr = ", ".join(tools.tess_languages()) or "chưa cài"
        QMessageBox.about(self, "Giới thiệu", f"<h3>{APP_NAME}</h3>"
                          f"<p><b>{APP_NAME} by {AUTHOR}</b><br>Phiên bản {VERSION}</p>"
                          "<p>Trình xem và chỉnh sửa PDF gọn nhẹ.</p>"
                          f"<p>Lõi PDF: PyMuPDF {pymupdf.VersionBind}<br>"
                          f"Chuyển Word/Excel → PDF: {'LibreOffice' if so else 'chưa có LibreOffice (dùng MS Office nếu có)'}<br>"
                          f"OCR (Tesseract): {ocr}</p>"
                          "<p>Mã nguồn dùng PyMuPDF (giấy phép AGPL) và pyHanko (MIT): dùng nội bộ thoải mái, "
                          "nếu phát hành cho người khác cần kèm mã nguồn.</p>")


def selftest(out: str | None = None) -> int:
    """Kiểm tra nhanh bản đóng gói: các thư viện và tài nguyên kèm theo có đủ không. Dùng khi build bộ cài."""
    import json
    rep: dict = {"version": VERSION, "frozen": tools.FROZEN, "app_dir": tools.app_dir()}

    def probe(name, fn):
        try:
            rep[name] = fn()
        except Exception as e:
            rep[name] = f"LOI: {type(e).__name__}: {e}"
    probe("pymupdf", lambda: pymupdf.__doc__.split()[1] if pymupdf.__doc__ else "ok")
    probe("pyhanko", lambda: bool(__import__("pyhanko.sign", fromlist=["signers"]).signers))
    probe("pkcs11", lambda: bool(__import__("pkcs11")))
    probe("pdf2docx", lambda: bool(__import__("pdf2docx")))
    probe("openpyxl", lambda: __import__("openpyxl").__version__)
    probe("fonts", lambda: bool(tools.pick_font_file("Arial", 0, "Tiếng Việt có dấu")[0]))
    probe("tessdata", lambda: tools.tess_languages())
    probe("rapidocr", lambda: __import__("litepdf.ocr", fromlist=["x"]).rapid_available())
    probe("soffice", lambda: tools.find_soffice())
    probe("data_dir", lambda: __import__("litepdf.dialogs", fromlist=["x"]).data_dir())

    def tess():
        d = pymupdf.open()
        pg = d.new_page()
        pg.insert_text((72, 100), "Hello OCR 123", fontsize=20)
        pix = pg.get_pixmap(dpi=150)
        one = pymupdf.open("pdf", pix.pdfocr_tobytes(language="eng", tessdata=tools.find_tessdata()))
        return one[0].get_text().strip()
    if rep.get("tessdata"):
        probe("tesseract_run", tess)

    def rapid():
        from . import ocr
        d = pymupdf.open()
        pg = d.new_page()
        pg.insert_text((72, 100), "Hello OCR 123", fontsize=20)
        out_ = {}
        for lang in ("multi", "latin"):
            eng = ocr.rapid_engine(lang, "")
            out_[lang] = [t for _b, t in ocr.rapid_lines(eng, ocr.pix_array(pg.get_pixmap(dpi=150)))]
        return out_
    if rep.get("rapidocr") is True:
        probe("rapidocr_run", rapid)
    text = json.dumps(rep, ensure_ascii=False, indent=1)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        print(text)
    return 0


def _instance_name() -> str:
    """Tên kênh nội bộ để các lần mở app của CÙNG một người dùng tìm thấy nhau."""
    import getpass
    import hashlib
    try:
        user = getpass.getuser()
    except Exception:
        user = "user"
    return "PDFEditorLite-" + hashlib.md5(user.encode("utf-8", "ignore")).hexdigest()[:10]


def send_to_running(files: list[str]) -> bool:
    """App đang mở sẵn thì chuyển các file cho cửa sổ đó mở thành tab mới. Trả về True nếu đã chuyển xong."""
    import json
    from PySide6.QtNetwork import QLocalSocket
    sock = QLocalSocket()
    sock.connectToServer(_instance_name())
    if not sock.waitForConnected(400):
        return False
    if sys.platform.startswith("win"):      # cho phép cửa sổ đang mở tự nổi lên trước (Windows mặc định chặn việc này)
        try:
            import ctypes
            ctypes.windll.user32.AllowSetForegroundWindow(-1)
        except Exception:
            pass
    sock.write(json.dumps({"files": files}).encode("utf-8"))
    sock.flush()
    sock.waitForBytesWritten(2000)
    # Đã nối được tức là có cửa sổ đang mở và nó sẽ nhận file. Chờ nó đóng kết nối (đã nhận xong) rồi thoát.
    if sock.state() != QLocalSocket.UnconnectedState:
        sock.waitForDisconnected(3000)
    return True


def listen_for_files(win) -> None:
    """Nhận file từ các lần mở app sau (nhấp đúp file khác...) và mở thành tab trong cửa sổ này."""
    import json
    from PySide6.QtNetwork import QLocalServer
    name = _instance_name()
    server = QLocalServer(win)
    if not server.listen(name):             # kênh cũ còn sót lại sau một lần app thoát đột ngột
        QLocalServer.removeServer(name)
        server.listen(name)

    def incoming():
        conn = server.nextPendingConnection()
        if conn is None:
            return

        def read():
            try:
                files = json.loads(bytes(conn.readAll()).decode("utf-8")).get("files", [])
            except Exception:
                files = []
            conn.write(b"ok")
            conn.flush()
            conn.disconnectFromServer()
            if win.isMinimized():
                win.showNormal()
            win.raise_()
            win.activateWindow()
            for f in files:
                if os.path.exists(f):
                    win.guard(lambda f=f: win.open_path(f))()
        conn.readyRead.connect(read)
    server.newConnection.connect(incoming)
    win._instance_server = server


def run(argv: list[str]) -> int:
    if len(argv) > 1 and argv[1] == "--selftest":
        return selftest(argv[2] if len(argv) > 2 else None)
    app = QApplication(argv)
    files = [os.path.abspath(a) for a in argv[1:] if not a.startswith("-") and os.path.exists(a)]
    lock = None
    try:        # đã có một cửa sổ PDF Editor Lite đang mở: giao file cho nó rồi thoát, không mở cửa sổ thứ hai
        import time
        from PySide6.QtCore import QDir, QLockFile
        if send_to_running(files):
            return 0
        # Chưa có cửa sổ nào nhận. Có thể nhiều file vừa được mở cùng lúc (chọn nhiều file rồi Enter): chỉ MỘT tiến trình
        # giữ được khoá và trở thành cửa sổ chính, các tiến trình còn lại chờ nó khởi động xong rồi giao file cho nó.
        lock = QLockFile(os.path.join(QDir.tempPath(), _instance_name() + ".lock"))
        lock.setStaleLockTime(0)
        if not lock.tryLock(0):
            end = time.time() + 25
            while time.time() < end:
                if send_to_running(files):
                    return 0
                if lock.tryLock(0):          # cửa sổ chính đã thoát giữa chừng: tiến trình này lên thay
                    break
                time.sleep(0.25)
    except Exception:
        pass
    app._instance_lock = lock
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(VERSION)
    app.setOrganizationName(AUTHOR)
    if sys.platform.startswith("win"):      # để thanh tác vụ Windows hiện biểu tượng của app thay vì biểu tượng Python
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"{AUTHOR}.PDFEditorLite")
        except Exception:
            pass
    from .icons import app_icon
    app.setWindowIcon(app_icon())
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor("#f6f7f9"))
    pal.setColor(QPalette.WindowText, QColor("#202124"))
    pal.setColor(QPalette.Base, QColor("#ffffff"))
    pal.setColor(QPalette.AlternateBase, QColor("#f1f3f4"))
    pal.setColor(QPalette.Text, QColor("#202124"))
    pal.setColor(QPalette.Button, QColor("#f1f3f4"))
    pal.setColor(QPalette.ButtonText, QColor("#202124"))
    pal.setColor(QPalette.Highlight, QColor("#1a73e8"))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
    pal.setColor(QPalette.ToolTipText, QColor("#202124"))
    pal.setColor(QPalette.PlaceholderText, QColor("#9aa0a6"))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):   # chữ của mục không khả dụng: xám nhạt
        pal.setColor(QPalette.Disabled, role, QColor("#b4b9c0"))
    pal.setColor(QPalette.Disabled, QPalette.Highlight, QColor("#e8eaed"))
    pal.setColor(QPalette.Disabled, QPalette.HighlightedText, QColor("#b4b9c0"))
    app.setPalette(pal)
    app.setStyleSheet("QToolBar{border:0;border-bottom:1px solid #dadce0;spacing:2px;padding:3px;background:#f6f7f9;}"
                      "QToolButton{padding:3px;border-radius:4px;} QToolButton:hover{background:#e3e6ea;}"
                      "QToolButton:checked{background:#d2e3fc;} QStatusBar{color:#3c4043;}"
                      "QMenu::item:disabled{color:#b4b9c0;} QToolButton:disabled{color:#b4b9c0;}")
    win = MainWindow()
    win.place_centered()
    win.show()
    try:
        listen_for_files(win)
    except Exception:
        pass
    for a in files:
        win.open_path(a)
    return app.exec()
