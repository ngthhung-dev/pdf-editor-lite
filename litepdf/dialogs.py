"""Các hộp thoại của PDF Editor Lite."""
from __future__ import annotations

import json
import os
import sys
import time

from PySide6.QtCore import QEvent, QPointF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap, qRgb
from PySide6.QtWidgets import (QFrame, QAbstractItemView, QCheckBox, QColorDialog, QComboBox, QDialog,
                               QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
                               QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMessageBox, QPlainTextEdit, QPushButton, QRadioButton, QScrollArea,
                               QSizePolicy, QSpinBox, QTextBrowser, QVBoxLayout, QWidget)

from . import signing
from . import tools

APP_DIR = tools.app_dir()


def data_dir() -> str:
    """Thư mục dữ liệu. Bản portable: nằm cạnh ứng dụng. Bản cài đặt (file .exe đóng gói): nằm trong hồ sơ người dùng,
    để cập nhật hay gỡ app không đụng tới key, cài đặt và bộ nhớ dịch."""
    if tools.FROZEN:
        base = os.environ.get("APPDATA") if sys.platform.startswith("win") else \
            os.path.join(os.path.expanduser("~"), "Library", "Application Support") if sys.platform == "darwin" else \
            os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
        d = os.path.join(base or os.path.expanduser("~"), "PDF Editor Lite")
        os.makedirs(d, exist_ok=True)
        return d
    d = os.path.join(APP_DIR, "data")
    try:
        os.makedirs(d, exist_ok=True)
        probe = os.path.join(d, ".w")
        open(probe, "w").close()
        os.unlink(probe)
    except OSError:
        d = os.path.join(os.path.expanduser("~"), ".litepdf")
        os.makedirs(d, exist_ok=True)
    return d


def sig_dir() -> str:
    d = os.path.join(data_dir(), "chu_ky")
    os.makedirs(d, exist_ok=True)
    return d


def trust_dir() -> str:
    d = os.path.join(data_dir(), "chung_thu_tin_cay")
    os.makedirs(d, exist_ok=True)
    return d


class Config(dict):
    def __init__(self):
        super().__init__()
        self.path = os.path.join(data_dir(), "config.json")
        try:
            with open(self.path, encoding="utf-8") as f:
                self.update(json.load(f))
        except Exception:
            pass

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self, f, ensure_ascii=False, indent=1)
        except Exception:
            pass


def fit_dialog(dlg, w: int, h: int) -> None:
    """Đặt cỡ hộp thoại nhưng không để vượt quá màn hình (màn hình nhỏ hoặc tỉ lệ hiển thị 125–150%)."""
    from PySide6.QtGui import QGuiApplication
    parent = dlg.parentWidget()
    screen = (parent.screen() if parent is not None else None) or QGuiApplication.primaryScreen()
    if screen is not None:
        area = screen.availableGeometry()
        w, h = min(w, area.width() - 30), min(h, area.height() - 70)
        dlg.resize(w, h)
        # gọi thẳng QWidget.move vì vài hộp thoại có hàm move() riêng để chuyển dòng trong danh sách
        QWidget.move(dlg, area.x() + (area.width() - w) // 2, area.y() + max(0, (area.height() - h - 32) // 2))
    else:
        dlg.resize(w, h)


def center_on_parent(dlg) -> None:
    """Đặt hộp thoại vào chính giữa cửa sổ app (vẫn giữ trọn trong màn hình)."""
    from PySide6.QtGui import QGuiApplication
    parent = dlg.parentWidget()
    if parent is None:
        return
    win = parent.window()
    g = win.frameGeometry()
    size = dlg.frameGeometry().size()
    x = g.x() + (g.width() - size.width()) // 2
    y = g.y() + (g.height() - size.height()) // 2
    screen = win.screen() or QGuiApplication.primaryScreen()
    if screen is not None:
        a = screen.availableGeometry()
        x = max(a.x(), min(x, a.right() - size.width() + 1))
        y = max(a.y(), min(y, a.bottom() - size.height() + 1))
    QWidget.move(dlg, x, y)


def _wrap_label(text: str) -> QLabel:
    lb = QLabel(text)
    lb.setWordWrap(True)
    return lb


def _buttons(dlg: QDialog, ok_text="OK") -> QDialogButtonBox:
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.button(QDialogButtonBox.Ok).setText(ok_text)
    bb.button(QDialogButtonBox.Cancel).setText("Huỷ")
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    return bb


class PreviewBox(QWidget):
    """Khung xem trước dùng chung: lăn chuột để chuyển trang, giữ Ctrl + lăn chuột để thu phóng."""
    step = Signal(int)       # +1: trang sau, -1: trang trước
    changed = Signal()       # mức phóng đổi, cần vẽ lại

    def __init__(self, parent=None):
        super().__init__(parent)
        self.zoom = 1.0      # 1.0 = vừa khung
        self._acc = 0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.area = QScrollArea()
        self.area.setWidget(self.label)
        self.area.setWidgetResizable(True)
        self.area.setAlignment(Qt.AlignCenter)
        self.area.setMinimumSize(QSize(300, 320))
        self.area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.area.setStyleSheet("QScrollArea{background:#dfe3e8;border:1px solid #c4c9d0;}"
                                "QLabel{background:#dfe3e8;color:#5f6368;}")
        lay.addWidget(self.area, 1)
        row = QHBoxLayout()
        hint = QLabel("Lăn chuột: chuyển trang  ·  Ctrl + lăn chuột: thu phóng")
        hint.setStyleSheet("color:#80868b")
        self.zoom_lb = QLabel("Vừa khung")
        self.zoom_lb.setStyleSheet("color:#3c4043")
        self.fit_btn = QPushButton("Vừa khung")
        self.fit_btn.setToolTip("Đưa khung xem trước về vừa khít")
        self.fit_btn.clicked.connect(self.reset)
        self.fit_btn.setEnabled(False)
        row.addWidget(hint)
        row.addStretch()
        row.addWidget(self.zoom_lb)
        row.addWidget(self.fit_btn)
        lay.addLayout(row)
        for w in (self.area.viewport(), self.label):
            w.installEventFilter(self)

    # -- cho hộp thoại gọi
    def scale(self, w_pt: float, h_pt: float) -> float:
        """Số điểm ảnh (logic) trên mỗi point để trang vừa khung, nhân với mức phóng hiện tại."""
        # tính theo kích thước khung (không theo vùng nhìn) để mức "vừa khung" không đổi khi thanh cuộn hiện ra
        full_w = self.area.width() - 2 * self.area.frameWidth() - 24
        full_h = self.area.height() - 2 * self.area.frameWidth() - 24
        fit = min(max(100, full_w) / max(1.0, w_pt), max(100, full_h) / max(1.0, h_pt))
        return fit * self.zoom

    def show_pixmap(self, pm: QPixmap):
        self.label.setText("")
        self.label.setPixmap(pm)

    def show_text(self, text: str):
        self.label.setPixmap(QPixmap())
        self.label.setText(text)

    def text(self) -> str:
        return self.label.text()

    def reset(self):
        self.set_zoom(1.0)

    def set_zoom(self, z: float):
        z = min(5.0, max(0.25, z))
        if abs(z - 1.0) < 0.04:
            z = 1.0
        if z == self.zoom:
            return
        hb, vb = self.area.horizontalScrollBar(), self.area.verticalScrollBar()
        fx = (hb.value() + hb.pageStep() / 2) / max(1, hb.maximum() + hb.pageStep())   # giữ nguyên chỗ đang nhìn
        fy = (vb.value() + vb.pageStep() / 2) / max(1, vb.maximum() + vb.pageStep())
        self.zoom = z
        self.zoom_lb.setText("Vừa khung" if z == 1.0 else f"{round(z * 100)}% so với vừa khung")
        self.fit_btn.setEnabled(z != 1.0)
        self.changed.emit()
        from PySide6.QtCore import QTimer
        QTimer.singleShot(140, lambda: (hb.setValue(int(fx * (hb.maximum() + hb.pageStep()) - hb.pageStep() / 2)),
                                        vb.setValue(int(fy * (vb.maximum() + vb.pageStep()) - vb.pageStep() / 2))))

    # -- chuột
    def eventFilter(self, obj, e):
        if e.type() == QEvent.Wheel:
            dy = e.angleDelta().y() or e.angleDelta().x()
            if e.modifiers() & Qt.ControlModifier:
                if dy:
                    self.set_zoom(self.zoom * (1.2 if dy > 0 else 1 / 1.2))
                return True
            vb = self.area.verticalScrollBar()
            if vb.maximum() > 0 and ((dy < 0 and vb.value() < vb.maximum()) or (dy > 0 and vb.value() > 0)):
                self._acc = 0
                return False   # đang phóng to và còn cuộn được: cuộn trong trang trước
            self._acc += dy
            if abs(self._acc) >= 120:   # một nấc lăn = một trang (bàn rê cảm ứng thì cộng dồn)
                n = int(self._acc / 120)
                self._acc -= n * 120
                self.step.emit(-1 if n > 0 else 1)
                if vb.maximum() > 0:   # sang trang mới thì bắt đầu ở đầu/cuối trang cho liền mạch
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(160, lambda: vb.setValue(0 if n < 0 else vb.maximum()))
            return True
        return False


class ColorButton(QPushButton):
    def __init__(self, color: QColor, parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 26)
        self._c = QColor(color)
        self.clicked.connect(self._pick)
        self._paint()

    def _paint(self):
        self.setStyleSheet(f"QPushButton{{background:{self._c.name()};border:1px solid #888;border-radius:4px;}}")

    def _pick(self):
        c = QColorDialog.getColor(self._c, self, "Chọn màu")
        if c.isValid():
            self._c = c
            self._paint()

    def color(self) -> QColor:
        return QColor(self._c)


class TextDialog(QDialog):
    def __init__(self, parent, title: str, text: str, size: float, color: QColor, single_line=False,
                 style: tuple[bool, bool] | None = None, note: str | None = None, family: str | None = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(520, 200 if single_line else 300)
        lay = QVBoxLayout(self)
        self.edit = QPlainTextEdit(text)
        f = self.edit.font()
        f.setPointSize(max(f.pointSize(), 11))
        self.edit.setFont(f)
        if single_line:
            self.edit.setMaximumHeight(80)
        lay.addWidget(self.edit)
        row = QHBoxLayout()
        row.addWidget(QLabel("Cỡ chữ:"))
        self.size_box = QDoubleSpinBox()
        self.size_box.setRange(3, 200)
        self.size_box.setDecimals(1)
        self.size_box.setValue(size)
        row.addWidget(self.size_box)
        row.addWidget(QLabel("Màu:"))
        self.col = ColorButton(color)
        row.addWidget(self.col)
        self.b = self.i = None
        if style is not None:
            self.b = QCheckBox("Đậm")
            self.b.setChecked(style[0])
            self.i = QCheckBox("Nghiêng")
            self.i.setChecked(style[1])
            row.addWidget(self.b)
            row.addWidget(self.i)
        self.fam = None
        if family is not None:
            self.fam = QComboBox()
            for key, name in (("arial", "Không chân (Arial)"), ("times", "Có chân (Times New Roman)"),
                              ("courier", "Đều nét (Courier)")):
                self.fam.addItem(name, key)
            self.fam.setCurrentIndex(max(0, self.fam.findData(family)))
            row.addWidget(QLabel("Phông:"))
            row.addWidget(self.fam)
        row.addStretch()
        lay.addLayout(row)
        if note:
            lb = QLabel(note)
            lb.setWordWrap(True)
            lb.setStyleSheet("color:#5f6368")
            lay.addWidget(lb)
        lay.addWidget(_buttons(self))
        self.edit.setFocus()
        self.edit.selectAll()

    def text(self) -> str:
        return self.edit.toPlainText()

    def size(self) -> float:
        return self.size_box.value()

    def color(self) -> QColor:
        return self.col.color()

    def family(self) -> str:
        return self.fam.currentData() if self.fam else "arial"

    def bold(self):
        return self.b.isChecked() if self.b else None

    def italic(self):
        return self.i.isChecked() if self.i else None


def form_dialog(parent, title: str, fields: list[tuple], note: str | None = None, ok_text="OK") -> dict | None:
    """fields: (khoá, nhãn, kiểu, mặc định[, lựa chọn]). Kiểu: str|password|int|float|bool|choice."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setMinimumWidth(420)
    lay = QVBoxLayout(dlg)
    if note:
        lb = QLabel(note)
        lb.setWordWrap(True)
        lay.addWidget(lb)
    form = QFormLayout()
    lay.addLayout(form)
    ws = {}
    for f in fields:
        key, label, kind, default = f[:4]
        if kind in ("str", "password"):
            w = QLineEdit(str(default or ""))
            if kind == "password":
                w.setEchoMode(QLineEdit.Password)
            if len(f) > 4:
                w.setPlaceholderText(f[4])
        elif kind == "int":
            w = QSpinBox()
            w.setRange(*(f[4] if len(f) > 4 else (1, 100000)))
            w.setValue(int(default))
        elif kind == "float":
            w = QDoubleSpinBox()
            w.setRange(*(f[4] if len(f) > 4 else (0, 10000)))
            w.setValue(float(default))
        elif kind == "bool":
            w = QCheckBox()
            w.setChecked(bool(default))
        else:
            w = QComboBox()
            for val, text in f[4]:
                w.addItem(text, val)
            w.setCurrentIndex(max(0, w.findData(default)))
        ws[key] = (kind, w)
        form.addRow(label, w)
    lay.addWidget(_buttons(dlg, ok_text))
    if not dlg.exec():
        return None
    out = {}
    for key, (kind, w) in ws.items():
        if kind in ("str", "password"):
            out[key] = w.text()
        elif kind in ("int", "float"):
            out[key] = w.value()
        elif kind == "bool":
            out[key] = w.isChecked()
        else:
            out[key] = w.currentData()
    return out


class FileListDialog(QDialog):
    """Chọn và sắp thứ tự nhiều file (gộp PDF, ghép ảnh)."""

    def __init__(self, parent, title: str, filt: str, paths: list[str] | None = None, hint: str = ""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(560, 400)
        self.filt = filt
        lay = QVBoxLayout(self)
        if hint:
            lay.addWidget(QLabel(hint))
        row = QHBoxLayout()
        self.list = QListWidget()
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        row.addWidget(self.list, 1)
        col = QVBoxLayout()
        for text, fn in (("Thêm file…", self.add), ("Bỏ khỏi danh sách", self.remove), ("Lên", lambda: self.move(-1)),
                         ("Xuống", lambda: self.move(1))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            col.addWidget(b)
        col.addStretch()
        row.addLayout(col)
        lay.addLayout(row)
        lay.addWidget(_buttons(self, "Tiếp tục"))
        for p in paths or []:
            self._add(p)

    def _add(self, p: str):
        it = QListWidgetItem(os.path.basename(p))
        it.setData(Qt.UserRole, p)
        it.setToolTip(p)
        self.list.addItem(it)

    def add(self):
        ps, _ = QFileDialog.getOpenFileNames(self, "Chọn file", "", self.filt)
        for p in ps:
            self._add(p)

    def remove(self):
        for it in self.list.selectedItems():
            self.list.takeItem(self.list.row(it))

    def move(self, d: int):
        r = self.list.currentRow()
        if r < 0 or not 0 <= r + d < self.list.count():
            return
        it = self.list.takeItem(r)
        self.list.insertItem(r + d, it)
        self.list.setCurrentRow(r + d)

    def paths(self) -> list[str]:
        return [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())]


class ReportDialog(QDialog):
    def __init__(self, parent, title: str, html_text: str):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(600, 460)
        lay = QVBoxLayout(self)
        tb = QTextBrowser()
        tb.setHtml(html_text)
        lay.addWidget(tb)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.button(QDialogButtonBox.Close).setText("Đóng")
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)


# ------------------------------------------------------------------ chữ ký tay
class _Pad(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(560, 220)
        self.paths: list[QPainterPath] = []
        self.color = QColor("#0b2e8a")
        self.setCursor(Qt.CrossCursor)

    def mousePressEvent(self, e):
        p = QPainterPath(QPointF(e.position()))
        self.paths.append(p)

    def mouseMoveEvent(self, e):
        if self.paths:
            self.paths[-1].lineTo(QPointF(e.position()))
            self.update()

    def _draw(self, p: QPainter, scale=1.0):
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(self.color, 2.4 * scale, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for path in self.paths:
            p.drawPath(path)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), Qt.white)
        p.setPen(QPen(QColor("#c0c4cc"), 1, Qt.DashLine))
        p.drawLine(20, self.height() - 50, self.width() - 20, self.height() - 50)
        self._draw(p)

    def image(self) -> QImage | None:
        if not self.paths:
            return None
        br = None
        for path in self.paths:
            br = path.boundingRect() if br is None else br.united(path.boundingRect())
        br = br.adjusted(-6, -6, 6, 6)
        k = 3
        img = QImage(int(br.width() * k), int(br.height() * k), QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.scale(k, k)
        p.translate(-br.topLeft())
        self._draw(p)
        p.end()
        return img


class SignaturePad(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Vẽ chữ ký")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Giữ chuột trái và ký vào khung bên dưới:"))
        self.pad = _Pad()
        lay.addWidget(self.pad)
        row = QHBoxLayout()
        clear = QPushButton("Vẽ lại")
        clear.clicked.connect(lambda: (self.pad.paths.clear(), self.pad.update()))
        row.addWidget(clear)
        row.addWidget(QLabel("Màu mực:"))
        for name, c in (("Xanh", "#0b2e8a"), ("Đen", "#111111"), ("Đỏ", "#c21807")):
            b = QPushButton(name)
            b.clicked.connect(lambda _=False, c=c: (setattr(self.pad, "color", QColor(c)), self.pad.update()))
            row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)
        lay.addWidget(_buttons(self, "Lưu chữ ký"))
        self.path = None

    def accept(self):
        img = self.pad.image()
        if img is None:
            QMessageBox.information(self, "Vẽ chữ ký", "Bạn chưa vẽ gì.")
            return
        self.path = os.path.join(sig_dir(), time.strftime("chuky_%Y%m%d_%H%M%S.png"))
        img.save(self.path)
        super().accept()


def remove_white_background(src: str, dst: str) -> None:
    """Biến nền trắng của ảnh chữ ký/con dấu thành trong suốt."""
    img = QImage(src)
    if img.isNull():
        raise ValueError("Không đọc được ảnh")
    if img.width() > 1600:
        img = img.scaledToWidth(1600, Qt.SmoothTransformation)
    gray = img.convertToFormat(QImage.Format_Grayscale8).convertToFormat(QImage.Format_Indexed8)
    # alpha = độ đậm của nét, tăng tương phản để nét mực không bị nhạt
    gray.setColorTable([qRgb(v, v, v) for v in (min(255, max(0, int((235 - g) * 3.2))) for g in range(256))])
    alpha = gray.convertToFormat(QImage.Format_Grayscale8)
    out = img.convertToFormat(QImage.Format_ARGB32)
    out.setAlphaChannel(alpha)
    out.save(dst)


class SignatureLibrary(QDialog):
    """Thư viện ảnh chữ ký tay / con dấu để chèn vào tài liệu."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Chữ ký tay và con dấu (ảnh)")
        self.resize(600, 380)
        lay = QVBoxLayout(self)
        note = QLabel("Ảnh chữ ký chỉ là hình chèn lên trang, <b>không phải chữ ký số</b>. "
                      "Hợp đồng cần giá trị pháp lý thì dùng mục Ký số.")
        note.setWordWrap(True)
        lay.addWidget(note)
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(QSize(170, 90))
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.itemDoubleClicked.connect(lambda _i: self.accept())
        lay.addWidget(self.list, 1)
        row = QHBoxLayout()
        for text, fn in (("Vẽ chữ ký mới…", self.draw), ("Thêm từ file ảnh…", self.from_file), ("Xoá", self.delete)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)
        lay.addWidget(_buttons(self, "Chèn vào trang"))
        self.reload()

    def reload(self, select: str | None = None):
        self.list.clear()
        for f in sorted(os.listdir(sig_dir())):
            if f.lower().endswith((".png", ".jpg", ".jpeg")):
                p = os.path.join(sig_dir(), f)
                pm = QPixmap(p)
                canvas = QPixmap(170, 90)
                canvas.fill(Qt.white)
                qp = QPainter(canvas)
                s = pm.scaled(162, 82, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                qp.drawPixmap((170 - s.width()) // 2, (90 - s.height()) // 2, s)
                qp.end()
                it = QListWidgetItem(QIcon(canvas), "")
                it.setData(Qt.UserRole, p)
                self.list.addItem(it)
                if p == select:
                    self.list.setCurrentItem(it)
        if self.list.count() and not self.list.currentItem():
            self.list.setCurrentRow(0)

    def draw(self):
        d = SignaturePad(self)
        if d.exec():
            self.reload(d.path)

    def from_file(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn ảnh chữ ký hoặc con dấu", "",
                                           "Ảnh (*.png *.jpg *.jpeg *.bmp *.webp)")
        if not p:
            return
        dst = os.path.join(sig_dir(), time.strftime("anh_%Y%m%d_%H%M%S.png"))
        ans = QMessageBox.question(self, "Tách nền", "Tách nền trắng của ảnh thành trong suốt?\n"
                                   "(Nên chọn Có với ảnh chụp chữ ký trên giấy trắng.)")
        try:
            if ans == QMessageBox.Yes:
                remove_white_background(p, dst)
            else:
                QImage(p).save(dst)
        except Exception as e:
            QMessageBox.warning(self, "Lỗi", str(e))
            return
        self.reload(dst)

    def delete(self):
        it = self.list.currentItem()
        if it and QMessageBox.question(self, "Xoá", "Xoá ảnh chữ ký này khỏi thư viện?") == QMessageBox.Yes:
            try:
                os.unlink(it.data(Qt.UserRole))
            except OSError:
                pass
            self.reload()

    def selected(self) -> str | None:
        it = self.list.currentItem()
        return it.data(Qt.UserRole) if it else None

    def accept(self):
        if not self.selected():
            QMessageBox.information(self, "Chữ ký", "Hãy vẽ hoặc thêm một ảnh chữ ký trước.")
            return
        super().accept()


# -------------------------------------------------------------------- ký số
class SignDialog(QDialog):
    def __init__(self, parent, cfg: Config, visible: bool, empty_fields: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle("Ký số tài liệu")
        self.setMinimumWidth(560)
        self.cfg = cfg
        self.visible = visible
        self.signer = None
        self.session: signing.TokenSession | None = None
        self.certs: list[dict] = []
        self.info: dict = {}
        lay = QVBoxLayout(self)

        src = QGroupBox("Chứng thư số")
        sl = QVBoxLayout(src)
        self.r_pfx = QRadioButton("File chứng thư (.pfx / .p12)")
        self.r_tok = QRadioButton("USB token (VNPT-CA, Viettel-CA, FPT-CA, BKAV-CA…)")
        sl.addWidget(self.r_pfx)
        self.w_pfx = QWidget()
        f1 = QFormLayout(self.w_pfx)
        f1.setContentsMargins(22, 0, 0, 6)
        row = QHBoxLayout()
        self.pfx_path = QLineEdit(cfg.get("pfx_path", ""))
        b = QPushButton("Chọn…")
        b.clicked.connect(self._browse_pfx)
        row.addWidget(self.pfx_path)
        row.addWidget(b)
        f1.addRow("File:", row)
        self.pfx_pw = QLineEdit()
        self.pfx_pw.setEchoMode(QLineEdit.Password)
        f1.addRow("Mật khẩu:", self.pfx_pw)
        sl.addWidget(self.w_pfx)
        sl.addWidget(self.r_tok)
        self.w_tok = QWidget()
        f2 = QFormLayout(self.w_tok)
        f2.setContentsMargins(22, 0, 0, 0)
        row = QHBoxLayout()
        self.lib = QComboBox()
        self.lib.setEditable(True)
        self.lib.setSizePolicy(self.pfx_path.sizePolicy())
        libs = []
        try:
            libs = signing.find_pkcs11_libs()
        except Exception:
            pass
        last = cfg.get("pkcs11_lib", "")
        if last and last not in libs and os.path.exists(last):
            libs.insert(0, last)
        self.lib.addItems(libs)
        if last in libs:
            self.lib.setCurrentText(last)
        if not libs:
            self.lib.setPlaceholderText("Chưa dò thấy trình điều khiển token, bấm Chọn… để chỉ file")
            self.lib.setCurrentText("")
        b = QPushButton("Chọn…")
        b.clicked.connect(self._browse_lib)
        row.addWidget(self.lib, 1)
        row.addWidget(b)
        f2.addRow("Driver token:", row)
        row = QHBoxLayout()
        self.pin = QLineEdit()
        self.pin.setEchoMode(QLineEdit.Password)
        b = QPushButton("Đọc chứng thư")
        b.clicked.connect(self._connect_token)
        row.addWidget(self.pin)
        row.addWidget(b)
        f2.addRow("Mã PIN:", row)
        self.cert_box = QComboBox()
        self.cert_box.currentIndexChanged.connect(self._show_cert)
        f2.addRow("Chứng thư:", self.cert_box)
        sl.addWidget(self.w_tok)
        self.cert_lb = QLabel("")
        self.cert_lb.setWordWrap(True)
        self.cert_lb.setStyleSheet("color:#3c4043")
        sl.addWidget(self.cert_lb)
        lay.addWidget(src)

        g = QGroupBox("Thông tin chữ ký")
        fl = QFormLayout(g)
        self.reason = QLineEdit(cfg.get("sign_reason", ""))
        self.reason.setPlaceholderText("Ví dụ: Tôi đồng ý với nội dung hợp đồng")
        self.location = QLineEdit(cfg.get("sign_location", ""))
        self.location.setPlaceholderText("Ví dụ: Hà Nội")
        fl.addRow("Lý do ký:", self.reason)
        fl.addRow("Nơi ký:", self.location)
        self.tsa = QLineEdit(cfg.get("tsa_url", ""))
        self.tsa.setPlaceholderText("Để trống nếu không cần. Ví dụ: http://timestamp.digicert.com")
        fl.addRow("Dấu thời gian (TSA):", self.tsa)
        self.field = QComboBox()
        self.field.addItem("Tạo ô chữ ký mới" + ("" if visible else " (chữ ký ẩn)"), "")
        for n in empty_fields or []:
            self.field.addItem(f"Ký vào ô có sẵn: {n}", n)
        if empty_fields:
            fl.addRow("Vị trí:", self.field)
        self.certify = QCheckBox("Khoá tài liệu sau khi ký (chỉ còn cho phép ký thêm / điền form)")
        fl.addRow("", self.certify)
        lay.addWidget(g)

        self.g_show = QGroupBox("Hình thức hiển thị")
        hl = QFormLayout(self.g_show)
        row = QHBoxLayout()
        self.c_name = QCheckBox("Người ký")
        self.c_org = QCheckBox("Đơn vị")
        self.c_time = QCheckBox("Thời gian")
        self.c_reason = QCheckBox("Lý do")
        for c, key, dv in ((self.c_name, "show_name", True), (self.c_org, "show_org", True),
                           (self.c_time, "show_time", True), (self.c_reason, "show_reason", False)):
            c.setChecked(cfg.get(key, dv))
            row.addWidget(c)
        row.addStretch()
        hl.addRow("Dòng chữ:", row)
        row = QHBoxLayout()
        self.img = QComboBox()
        self.img.addItem("Không dùng ảnh", "")
        for f in sorted(os.listdir(sig_dir())):
            if f.lower().endswith((".png", ".jpg", ".jpeg")):
                self.img.addItem(f, os.path.join(sig_dir(), f))
        i = self.img.findData(cfg.get("sign_image", ""))
        self.img.setCurrentIndex(max(0, i))
        b = QPushButton("Thư viện chữ ký…")
        b.clicked.connect(self._library)
        row.addWidget(self.img, 1)
        row.addWidget(b)
        hl.addRow("Ảnh chữ ký/con dấu:", row)
        self.g_show.setVisible(visible or bool(empty_fields))
        lay.addWidget(self.g_show)

        lay.addWidget(_buttons(self, "Ký"))
        (self.r_tok if cfg.get("sign_source") == "token" else self.r_pfx).setChecked(True)
        self.r_pfx.toggled.connect(self._toggle)
        self._toggle()

    def _toggle(self):
        self.w_pfx.setEnabled(self.r_pfx.isChecked())
        self.w_tok.setEnabled(self.r_tok.isChecked())
        self.cert_lb.setText("")
        if self.r_tok.isChecked():
            self._show_cert()

    def _browse_pfx(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn file chứng thư", "", "Chứng thư (*.pfx *.p12);;Tất cả (*)")
        if p:
            self.pfx_path.setText(p)

    def _browse_lib(self):
        filt = {"win32": "Thư viện (*.dll)", "darwin": "Thư viện (*.dylib *.so)"}.get(sys.platform, "Thư viện (*.so *.so.*)")
        start = r"C:\Windows\System32" if sys.platform.startswith("win") else "/usr/lib"
        p, _ = QFileDialog.getOpenFileName(self, "Chọn trình điều khiển PKCS#11 của token", start, filt + ";;Tất cả (*)")
        if p:
            self.lib.setCurrentText(p)

    def _library(self):
        d = SignatureLibrary(self)
        d.exec()
        cur = d.selected() or self.img.currentData()
        self.img.clear()
        self.img.addItem("Không dùng ảnh", "")
        for f in sorted(os.listdir(sig_dir())):
            if f.lower().endswith((".png", ".jpg", ".jpeg")):
                self.img.addItem(f, os.path.join(sig_dir(), f))
        self.img.setCurrentIndex(max(0, self.img.findData(cur)))

    def _connect_token(self):
        lib = self.lib.currentText().strip()
        if not lib or not os.path.exists(lib):
            QMessageBox.warning(self, "USB token", "Chưa chọn trình điều khiển (file PKCS#11) của token.\n\n"
                                "File này được cài cùng phần mềm quản lý token của nhà cung cấp, "
                                "thường nằm trong C:\\Windows\\System32 (ví dụ vnpt-ca_csp11.dll, viettel-ca_v6.dll).")
            return
        if not self.pin.text():
            QMessageBox.warning(self, "USB token", "Hãy nhập mã PIN của token.")
            return
        try:
            toks = signing.list_tokens(lib)
            if not toks:
                raise signing.SignError("Không thấy token nào đang cắm. Kiểm tra lại USB token.")
            if self.session:
                self.session.close()
            named = [t for t in toks if t["label"]] or toks
            tok = named[0]
            if len(named) > 1:
                names = [f"{t['label']} (khe {t['slot']})" for t in named]
                pick, ok = QInputDialog.getItem(self, "USB token", "Máy đang cắm nhiều token, chọn token để ký:",
                                                names, 0, False)
                if not ok:
                    return
                tok = named[names.index(pick)]
            self.session = signing.TokenSession(lib, tok, self.pin.text())
            self.certs = self.session.certificates()
        except signing.SignError as e:
            QMessageBox.warning(self, "USB token", str(e))
            return
        except Exception as e:
            QMessageBox.warning(self, "USB token", f"Lỗi khi đọc token: {type(e).__name__}: {e}")
            return
        self.cert_box.clear()
        for c in self.certs:
            i = c["info"]
            self.cert_box.addItem(f"{i['cn']}  (hết hạn {i['not_after']:%d/%m/%Y})")
        if not self.certs:
            QMessageBox.warning(self, "USB token", "Token không có chứng thư nào dùng để ký.")
        self.cfg["pkcs11_lib"] = lib
        self._show_cert()

    def _show_cert(self):
        i = self.cert_box.currentIndex()
        if self.r_tok.isChecked() and 0 <= i < len(self.certs):
            self._describe(self.certs[i]["info"])

    def _describe(self, info: dict):
        self.info = info
        warn = "  <b style='color:#d93025'>ĐÃ HẾT HẠN</b>" if info.get("expired") else ""
        self.cert_lb.setText(f"Người ký: <b>{info['cn']}</b><br>Cấp bởi: {info['issuer']}<br>"
                             f"Hiệu lực: {info['not_before']:%d/%m/%Y} – {info['not_after']:%d/%m/%Y}{warn}")

    def accept(self):
        try:
            if self.r_pfx.isChecked():
                p = self.pfx_path.text().strip()
                if not p or not os.path.exists(p):
                    raise signing.SignError("Hãy chọn file chứng thư .pfx hoặc .p12.")
                self.signer = signing.load_pfx(p, self.pfx_pw.text())
                self._describe(signing.cert_info(self.signer.signing_cert))
                self.cfg["pfx_path"] = p
            else:
                i = self.cert_box.currentIndex()
                if not self.session or not 0 <= i < len(self.certs):
                    raise signing.SignError("Hãy nhập PIN, bấm “Đọc chứng thư” và chọn chứng thư để ký.")
                self.signer = self.session.signer(self.certs[i])
                self._describe(self.certs[i]["info"])
        except signing.SignError as e:
            QMessageBox.warning(self, "Ký số", str(e))
            return
        except Exception as e:
            QMessageBox.warning(self, "Ký số", f"{type(e).__name__}: {e}")
            return
        if self.info.get("expired"):
            if QMessageBox.question(self, "Ký số", "Chứng thư này đã hết hạn, chữ ký sẽ không có giá trị. Vẫn ký?") \
                    != QMessageBox.Yes:
                return
        c = self.cfg
        c["sign_source"] = "token" if self.r_tok.isChecked() else "pfx"
        c["sign_reason"], c["sign_location"], c["tsa_url"] = self.reason.text(), self.location.text(), self.tsa.text().strip()
        c["show_name"], c["show_org"] = self.c_name.isChecked(), self.c_org.isChecked()
        c["show_time"], c["show_reason"] = self.c_time.isChecked(), self.c_reason.isChecked()
        c["sign_image"] = self.img.currentData() or ""
        c.save()
        super().accept()

    def lines(self) -> list[str]:
        out = []
        if self.c_name.isChecked():
            out.append("Ký bởi: " + self.info.get("cn", ""))
        if self.c_org.isChecked() and self.info.get("org") and self.info["org"] != self.info.get("cn"):
            out.append("Đơn vị: " + self.info["org"])
        if self.c_time.isChecked():
            tz = time.strftime("%z")
            out.append("Ngày ký: " + time.strftime("%d/%m/%Y %H:%M:%S") + (f" {tz[:3]}:{tz[3:]}" if tz else ""))
        if self.c_reason.isChecked() and self.reason.text().strip():
            out.append("Lý do: " + self.reason.text().strip())
        return out

    def close_session(self):
        if self.session:
            self.session.close()
            self.session = None


# ----------------------------------------------------------- ảnh -> PDF có xem trước
class ImagesToPdfDialog(QDialog):
    """Chọn ảnh, sắp thứ tự, chỉnh khổ trang và xem trước từng trang trước khi tạo PDF."""
    FILTER = "Ảnh (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp *.jfif)"
    ROT = Qt.UserRole + 1

    def __init__(self, parent, cfg: dict | None = None, paths: list[str] | None = None):
        super().__init__(parent)
        from PySide6.QtCore import QTimer
        self.setWindowTitle("Ghép nhiều ảnh thành một PDF")
        fit_dialog(self, 1060, 700)
        self.setAcceptDrops(True)
        self.cfg = cfg if cfg is not None else {}
        saved = self.cfg.get("img2pdf", {})
        root = QHBoxLayout(self)
        left = QVBoxLayout()
        root.addLayout(left, 4)
        left.addWidget(_wrap_label("Thêm ảnh (hoặc kéo thả ảnh vào đây), kéo trong danh sách để sắp thứ tự trang:"))
        row = QHBoxLayout()
        self.list = QListWidget()
        self.list.setIconSize(QSize(56, 56))
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.setMinimumWidth(240)
        self.list.currentRowChanged.connect(self._changed)
        self.list.model().rowsMoved.connect(self._changed)
        row.addWidget(self.list, 1)
        col = QVBoxLayout()
        for text, fn in (("Thêm ảnh…", self.add), ("Bỏ khỏi danh sách", self.remove), ("Lên", lambda: self.move(-1)),
                         ("Xuống", lambda: self.move(1)), ("Xoay trái 90°", lambda: self.rotate(-90)),
                         ("Xoay phải 90°", lambda: self.rotate(90)), ("Sắp theo tên", self.sort)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            col.addWidget(b)
        col.addStretch()
        row.addLayout(col)
        left.addLayout(row, 1)

        g = QGroupBox("Trang PDF")
        f = QFormLayout(g)
        self.size = QComboBox()
        self.size.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.size.setMinimumContentsLength(16)
        for k, t in (("image", "Bằng đúng kích thước ảnh"), ("A4", "A4 (210 × 297 mm)"), ("A3", "A3 (297 × 420 mm)"),
                     ("A5", "A5 (148 × 210 mm)"), ("Letter", "Letter (216 × 279 mm)"), ("Legal", "Legal (216 × 356 mm)")):
            self.size.addItem(t, k)
        self.size.setCurrentIndex(max(0, self.size.findData(saved.get("size", "A4"))))
        f.addRow("Khổ trang:", self.size)
        self.orient = QComboBox()
        self.orient.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.orient.setMinimumContentsLength(16)
        for k, t in (("portrait", "Dọc (mọi trang như nhau)"), ("landscape", "Ngang (mọi trang như nhau)"),
                     ("auto", "Tự động: ảnh ngang thì trang ngang")):
            self.orient.addItem(t, k)
        self.orient.setCurrentIndex(max(0, self.orient.findData(saved.get("orientation2", "portrait"))))
        f.addRow("Hướng trang:", self.orient)
        self.fit = QComboBox()
        self.fit.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.fit.setMinimumContentsLength(16)
        for k, t in (("fit", "Vừa trong trang, giữ nguyên ảnh (có thể dư lề trắng)"),
                     ("fill", "Lấp kín trang, cắt bớt mép ảnh"), ("stretch", "Kéo giãn kín trang (ảnh bị méo)")):
            self.fit.addItem(t, k)
        self.fit.setCurrentIndex(max(0, self.fit.findData(saved.get("fit", "fit"))))
        f.addRow("Cách đặt ảnh:", self.fit)
        self.margin = QSpinBox()
        self.margin.setRange(0, 50)
        self.margin.setSuffix(" mm")
        self.margin.setValue(int(saved.get("margin", 0)))
        f.addRow("Lề quanh ảnh:", self.margin)
        self.enlarge = QCheckBox("Phóng ảnh nhỏ cho vừa trang")
        self.enlarge.setChecked(saved.get("enlarge", True))
        f.addRow("", self.enlarge)
        left.addWidget(g)
        self.summary = QLabel("")
        self.summary.setStyleSheet("color:#3c4043")
        left.addWidget(self.summary)
        bb = _buttons(self, "Tạo PDF")
        self.ok_btn = bb.button(QDialogButtonBox.Ok)
        left.addWidget(bb)

        right = QVBoxLayout()
        root.addLayout(right, 5)
        self.preview = PreviewBox()
        self.preview.step.connect(lambda d: self.list.setCurrentRow(
            max(0, min(self.list.count() - 1, self.list.currentRow() + d))))
        self.preview.changed.connect(lambda: self._timer.start())
        right.addWidget(self.preview, 1)
        nav = QHBoxLayout()
        self.b_prev = QPushButton("◀ Trang trước")
        self.b_next = QPushButton("Trang sau ▶")
        self.page_lb = QLabel("")
        self.page_lb.setAlignment(Qt.AlignCenter)
        self.b_prev.clicked.connect(lambda: self.list.setCurrentRow(self.list.currentRow() - 1))
        self.b_next.clicked.connect(lambda: self.list.setCurrentRow(self.list.currentRow() + 1))
        nav.addWidget(self.b_prev)
        nav.addWidget(self.page_lb, 1)
        nav.addWidget(self.b_next)
        right.addLayout(nav)

        self._timer = QTimer(self, singleShot=True, interval=80, timeout=self._refresh)
        self.size.currentIndexChanged.connect(self._changed)
        self.orient.currentIndexChanged.connect(self._changed)
        self.fit.currentIndexChanged.connect(self._changed)
        self.margin.valueChanged.connect(self._changed)
        self.enlarge.toggled.connect(self._changed)
        for p in paths or []:
            self._add(p)
        if self.list.count():
            self.list.setCurrentRow(0)
        self._changed()

    # ------------------------------------------------------------ danh sách
    def _thumb(self, path: str, rot: int) -> QIcon:
        from PySide6.QtGui import QImageReader, QTransform
        r = QImageReader(path)
        sz = r.size()
        if sz.isValid() and max(sz.width(), sz.height()) > 0:
            k = 112 / max(sz.width(), sz.height())
            r.setScaledSize(QSize(max(1, int(sz.width() * k)), max(1, int(sz.height() * k))))
        img = r.read()
        if img.isNull():
            return QIcon()
        if rot:
            img = img.transformed(QTransform().rotate(rot))
        return QIcon(QPixmap.fromImage(img))

    def _add(self, p: str):
        from . import tools
        rot = tools.exif_rotation(p)
        it = QListWidgetItem(self._thumb(p, rot), os.path.basename(p))
        it.setData(Qt.UserRole, p)
        it.setData(self.ROT, rot)
        it.setToolTip(p)
        self.list.addItem(it)

    def add(self):
        ps, _ = QFileDialog.getOpenFileNames(self, "Chọn ảnh", self.cfg.get("last_dir", ""), self.FILTER)
        for p in ps:
            self._add(p)
        if ps:
            self.cfg["last_dir"] = os.path.dirname(ps[0])
            if self.list.currentRow() < 0:
                self.list.setCurrentRow(0)
        self._changed()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        exts = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp", ".jfif")
        for u in e.mimeData().urls():
            if u.isLocalFile() and u.toLocalFile().lower().endswith(exts):
                self._add(u.toLocalFile())
        if self.list.count() and self.list.currentRow() < 0:
            self.list.setCurrentRow(0)
        self._changed()

    def remove(self):
        for it in self.list.selectedItems():
            self.list.takeItem(self.list.row(it))
        self._changed()

    def move(self, d: int):
        r = self.list.currentRow()
        if r < 0 or not 0 <= r + d < self.list.count():
            return
        it = self.list.takeItem(r)
        self.list.insertItem(r + d, it)
        self.list.setCurrentRow(r + d)
        self._changed()

    def sort(self):
        self.list.sortItems()
        self._changed()

    def rotate(self, deg: int):
        items = self.list.selectedItems() or ([self.list.currentItem()] if self.list.currentItem() else [])
        for it in items:
            rot = (it.data(self.ROT) + deg) % 360
            it.setData(self.ROT, rot)
            it.setIcon(self._thumb(it.data(Qt.UserRole), rot))
        self._changed()

    # ------------------------------------------------------------ kết quả
    def paths(self) -> list[str]:
        return [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())]

    def options(self) -> dict:
        return {"size": self.size.currentData(), "orientation": self.orient.currentData(),
                "margin_mm": self.margin.value(), "enlarge": self.enlarge.isChecked(),
                "fit": self.fit.currentData(),
                "rotations": [self.list.item(i).data(self.ROT) for i in range(self.list.count())]}

    def _changed(self, *_):
        fixed = self.size.currentData() != "image"
        self.orient.setEnabled(fixed)
        self.fit.setEnabled(fixed)
        self.enlarge.setEnabled(fixed and self.fit.currentData() == "fit")
        self._timer.start()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._timer.start()

    def _refresh(self):
        import pymupdf
        from . import tools
        n = self.list.count()
        r = self.list.currentRow()
        self.ok_btn.setEnabled(n > 0)
        self.b_prev.setEnabled(r > 0)
        self.b_next.setEnabled(0 <= r < n - 1)
        if n == 0 or r < 0:
            self.preview.show_text("Chưa có ảnh nào.\nBấm “Thêm ảnh…” hoặc kéo thả ảnh vào cửa sổ này." if n == 0
                                 else "Chọn một ảnh trong danh sách để xem trước")
            self.page_lb.setText("")
            self.summary.setText(f"{n} ảnh → {n} trang" if n else "")
            return
        it = self.list.item(r)
        o = self.options()
        try:
            doc = pymupdf.open()
            tools.add_image_page(doc, it.data(Qt.UserRole), o["size"], o["orientation"], o["margin_mm"],
                                 it.data(self.ROT), o["enlarge"], fit=o["fit"])
            page = doc[0]
            dpr = self.devicePixelRatioF()
            k = self.preview.scale(page.rect.width, page.rect.height)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(k * dpr, k * dpr), alpha=False)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
            w_mm, h_mm = page.rect.width * 25.4 / 72, page.rect.height * 25.4 / 72
            info = doc.get_page_images(0)
            px = f"{info[0][2]} × {info[0][3]} px" if info else ""
            doc.close()
        except Exception as e:
            self.preview.show_text(f"Không đọc được ảnh này:\n{e}")
            self.page_lb.setText(f"Trang {r + 1} / {n}")
            return
        p = QPainter(img)
        p.setPen(QColor("#9aa0a6"))
        p.drawRect(0, 0, img.width() - 1, img.height() - 1)
        p.end()
        pm = QPixmap.fromImage(img)
        pm.setDevicePixelRatio(dpr)
        self.preview.show_pixmap(pm)
        self.page_lb.setText(f"Trang {r + 1} / {n}")
        name = ""
        if o["size"] != "image":
            name = f"{o['size']} {'ngang' if w_mm > h_mm else 'dọc'}, "
        self.summary.setText(f"{n} ảnh → {n} trang.  Trang {r + 1}: {name}{w_mm:.0f} × {h_mm:.0f} mm, ảnh gốc {px}")

    def accept(self):
        if not self.list.count():
            return
        o = self.options()
        self.cfg["img2pdf"] = {"size": o["size"], "orientation2": o["orientation"], "margin": o["margin_mm"],
                               "enlarge": o["enlarge"], "fit": o["fit"]}
        super().accept()


# ----------------------------------------------------------- gộp nhiều file có xem trước
class MergeDialog(QDialog):
    """Chọn file, sắp thứ tự, chọn trang cần lấy và xem trước kết quả gộp trước khi tạo PDF."""
    ID = Qt.UserRole + 1
    RANGE = Qt.UserRole + 2

    def __init__(self, parent, cfg: dict | None, filt: str, paths: list[str] | None = None):
        super().__init__(parent)
        from PySide6.QtCore import QTimer
        self.setWindowTitle("Gộp nhiều file thành một PDF")
        fit_dialog(self, 1080, 720)
        self.setAcceptDrops(True)
        self.cfg = cfg if cfg is not None else {}
        self.filt = filt
        self.docs: dict[int, object] = {}     # id -> pymupdf.Document
        self.is_image: dict[int, bool] = {}
        self._next = 1
        self.plan: list[tuple[int, int]] = []  # (id, trang nguồn) cho từng trang kết quả
        self.err = ""
        self.first_of: dict[int, int] = {}
        self.page = 0
        root = QHBoxLayout(self)
        left = QVBoxLayout()
        root.addLayout(left, 4)
        left.addWidget(_wrap_label("Thêm file (PDF, ảnh, Word, Excel…) hoặc kéo thả vào đây, kéo trong danh sách để sắp thứ tự:"))
        row = QHBoxLayout()
        self.list = QListWidget()
        self.list.setIconSize(QSize(44, 58))
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.setMinimumWidth(240)
        self.list.currentRowChanged.connect(self._file_selected)
        self.list.model().rowsMoved.connect(self._changed)
        row.addWidget(self.list, 1)
        col = QVBoxLayout()
        for text, fn in (("Thêm file…", self.add), ("Bỏ khỏi danh sách", self.remove), ("Lên", lambda: self.move(-1)),
                         ("Xuống", lambda: self.move(1)), ("Sắp theo tên", self.sort)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            col.addWidget(b)
        col.addStretch()
        row.addLayout(col)
        left.addLayout(row, 1)

        g = QGroupBox("Tuỳ chọn")
        f = QFormLayout(g)
        self.range = QLineEdit()
        self.range.setPlaceholderText("Để trống = lấy mọi trang. Ví dụ: 1-3, 5, 8-")
        self.range.textEdited.connect(self._range_edited)
        self.range_lb = QLabel("Trang lấy từ file đang chọn:")
        f.addRow(self.range_lb, self.range)
        self.size = QComboBox()
        self.size.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.size.setMinimumContentsLength(16)
        for k, t in (("", "Giữ nguyên khổ từng trang (ảnh đặt lên A4)"), ("A4", "Đưa tất cả về A4 (210 × 297 mm)"),
                     ("A3", "Đưa tất cả về A3 (297 × 420 mm)"), ("A5", "Đưa tất cả về A5 (148 × 210 mm)"),
                     ("Letter", "Đưa tất cả về Letter (216 × 279 mm)")):
            self.size.addItem(t, k)
        self.size.setCurrentIndex(max(0, self.size.findData(self.cfg.get("merge_size", ""))))
        self.size.currentIndexChanged.connect(self._reload_images)
        f.addRow("Khổ trang kết quả:", self.size)
        self.orient = QComboBox()
        self.orient.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.orient.setMinimumContentsLength(16)
        for k, t in (("portrait", "Dọc, mọi trang như nhau"), ("landscape", "Ngang, mọi trang như nhau"),
                     ("auto", "Theo từng trang gốc (trang ngang giữ ngang)")):
            self.orient.addItem(t, k)
        self.orient.setCurrentIndex(max(0, self.orient.findData(self.cfg.get("merge_orient", "portrait"))))
        self.orient.currentIndexChanged.connect(self._reload_images)
        f.addRow("Hướng trang:", self.orient)
        note = QLabel("Trang khác khổ hoặc khác hướng sẽ được co giãn cho vừa, giữ tỉ lệ và canh giữa trang.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#5f6368")
        f.addRow("", note)
        self.flat: dict = {}   # bản sao phục vụ co giãn trang, dùng lại giữa các lần xem trước
        left.addWidget(g)
        self.summary = QLabel("")
        self.summary.setStyleSheet("color:#3c4043")
        self.summary.setWordWrap(True)
        left.addWidget(self.summary)
        bb = _buttons(self, "Tạo PDF")
        self.ok_btn = bb.button(QDialogButtonBox.Ok)
        left.addWidget(bb)

        right = QVBoxLayout()
        root.addLayout(right, 5)
        self.preview = PreviewBox()
        self.preview.step.connect(self._step)
        self.preview.changed.connect(lambda: self._timer.start())
        right.addWidget(self.preview, 1)
        nav = QHBoxLayout()
        self.b_prev = QPushButton("◀ Trang trước")
        self.b_next = QPushButton("Trang sau ▶")
        self.page_lb = QLabel("")
        self.page_lb.setAlignment(Qt.AlignCenter)
        self.b_prev.clicked.connect(lambda: self._step(-1))
        self.b_next.clicked.connect(lambda: self._step(1))
        nav.addWidget(self.b_prev)
        nav.addWidget(self.page_lb, 1)
        nav.addWidget(self.b_next)
        right.addLayout(nav)

        self._timer = QTimer(self, singleShot=True, interval=80, timeout=self._refresh)
        for p in paths or []:
            self._add(p)
        if self.list.count():
            self.list.setCurrentRow(0)
        self._changed()

    # ------------------------------------------------------------ nạp file
    def _open(self, path: str):
        """Đổi file bất kỳ sang PDF trong bộ nhớ. Trả về (doc, là_ảnh)."""
        from . import tools
        ext = os.path.splitext(path)[1].lower()
        if ext in tools.IMAGE_EXT:
            fixed = bool(self.size.currentData())
            data = tools.images_to_pdf([path], size=self.size.currentData() or "A4",
                                       orientation=self.orient.currentData() if fixed else "auto")
            return tools.open_pdf_bytes(data)[0], True
        data, _eng = tools.any_to_pdf_bytes(path)
        pw = None
        while True:
            try:
                return tools.open_pdf_bytes(data, pw)[0], False
            except PermissionError:
                pw, ok = QInputDialog.getText(self, "File có mật khẩu",
                                              ("Mật khẩu chưa đúng, nhập lại:\n" if pw is not None
                                               else "Nhập mật khẩu để mở:\n") + os.path.basename(path),
                                              QLineEdit.Password)
                if not ok:
                    return None, False

    def _icon(self, doc) -> QIcon:
        import pymupdf
        try:
            page = doc[0]
            k = min(88 / page.rect.width, 116 / page.rect.height)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(k, k), alpha=False)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
            p = QPainter(img)
            p.setPen(QColor("#b0b6be"))
            p.drawRect(0, 0, img.width() - 1, img.height() - 1)
            p.end()
            return QIcon(QPixmap.fromImage(img))
        except Exception:
            return QIcon()

    def _label(self, it):
        doc = self.docs[it.data(self.ID)]
        n = doc.page_count
        rng = (it.data(self.RANGE) or "").strip()
        extra = f"{n} trang" if not rng else f"lấy trang {rng} / {n}"
        it.setText(f"{os.path.basename(it.data(Qt.UserRole))}\n{extra}")

    def _add(self, path: str) -> bool:
        from PySide6.QtWidgets import QApplication
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            doc, is_img = self._open(path)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Gộp file", f"Không đọc được file:\n{os.path.basename(path)}\n\n{e}")
            return False
        finally:
            while QApplication.overrideCursor():
                QApplication.restoreOverrideCursor()
        if doc is None:
            return False
        fid = self._next
        self._next += 1
        self.docs[fid] = doc
        self.is_image[fid] = is_img
        it = QListWidgetItem(self._icon(doc), "")
        it.setData(Qt.UserRole, path)
        it.setData(self.ID, fid)
        it.setData(self.RANGE, "")
        it.setToolTip(path)
        self.list.addItem(it)
        self._label(it)
        return True

    def add(self):
        ps, _ = QFileDialog.getOpenFileNames(self, "Chọn file", self.cfg.get("last_dir", ""), self.filt)
        for p in ps:
            self._add(p)
        if ps:
            self.cfg["last_dir"] = os.path.dirname(ps[0])
            if self.list.currentRow() < 0:
                self.list.setCurrentRow(0)
        self._changed()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        from . import tools
        for u in e.mimeData().urls():
            if u.isLocalFile() and os.path.splitext(u.toLocalFile())[1].lower() in tools.ALL_INPUT_EXT:
                self._add(u.toLocalFile())
        if self.list.count() and self.list.currentRow() < 0:
            self.list.setCurrentRow(0)
        self._changed()

    def _reload_images(self):
        for i in range(self.list.count()):
            it = self.list.item(i)
            fid = it.data(self.ID)
            if self.is_image.get(fid):
                try:
                    doc, _ = self._open(it.data(Qt.UserRole))
                    self.flat.pop(id(self.docs[fid]), None)
                    self.docs[fid].close()
                    self.docs[fid] = doc
                    it.setIcon(self._icon(doc))
                except Exception:
                    pass
        self._changed()

    # ------------------------------------------------------------ danh sách
    def remove(self):
        for it in self.list.selectedItems():
            fid = it.data(self.ID)
            self.list.takeItem(self.list.row(it))
            d = self.docs.pop(fid, None)
            if d is not None:
                self.flat.pop(id(d), None)
                d.close()
        self._changed()

    def move(self, d: int):
        r = self.list.currentRow()
        if r < 0 or not 0 <= r + d < self.list.count():
            return
        it = self.list.takeItem(r)
        self.list.insertItem(r + d, it)
        self.list.setCurrentRow(r + d)
        self._changed()

    def sort(self):
        self.list.sortItems()
        self._changed()

    def _file_selected(self, row: int):
        it = self.list.item(row) if row >= 0 else None
        self.range.blockSignals(True)
        self.range.setText(it.data(self.RANGE) if it else "")
        self.range.blockSignals(False)
        self.range.setEnabled(it is not None)
        self._changed(jump=True)

    def _range_edited(self, text: str):
        it = self.list.currentItem()
        if it:
            it.setData(self.RANGE, text.strip())
            self._label(it)
            self._changed(jump=True)

    # ------------------------------------------------------------ kết quả
    def _build_plan(self) -> str:
        """Lập danh sách trang kết quả. Trả về thông báo lỗi nếu có khoảng trang sai."""
        from . import tools
        self.plan = []
        self.first_of: dict[int, int] = {}
        err = ""
        for i in range(self.list.count()):
            it = self.list.item(i)
            fid = it.data(self.ID)
            doc = self.docs[fid]
            try:
                pages = tools.parse_ranges(it.data(self.RANGE) or "", doc.page_count)
            except tools.PdfError as e:
                err = f"{os.path.basename(it.data(Qt.UserRole))}: {e}"
                pages = []
            self.first_of[fid] = len(self.plan)
            self.plan += [(fid, p) for p in pages]
        return err

    def parts(self) -> list:
        out: list = []
        for fid, p in self.plan:
            if out and out[-1][0] is self.docs[fid] and out[-1][2] == fid:
                out[-1][1].append(p)
            else:
                out.append([self.docs[fid], [p], fid])
        return [(d, pages) for d, pages, _ in out]

    def result_bytes(self, progress=None) -> bytes:
        from . import tools
        return tools.merge_docs(self.parts(), progress, size=self.size.currentData() or None,
                                orientation=self.orient.currentData())

    def _changed(self, *_a, jump: bool = False):
        self.orient.setEnabled(bool(self.size.currentData()))
        self.err = self._build_plan()
        it = self.list.currentItem()
        if jump and it is not None:
            self.page = self.first_of.get(it.data(self.ID), 0)
        self.range.setStyleSheet("QLineEdit{border:1px solid #d93025;}" if self.err and it and
                                 self.err.startswith(os.path.basename(it.data(Qt.UserRole))) else "")
        self._timer.start()

    def _step(self, d: int):
        self.page += d
        self._refresh()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._timer.start()

    def _uniform_text(self) -> str:
        """Cho biết các trang kết quả có cùng một khổ và hướng hay không."""
        from . import tools
        size, orient = self.size.currentData(), self.orient.currentData()
        kinds = set()
        for fid, p in self.plan:
            r = self.docs[fid][p].rect
            if size in tools.PAPER_PT:
                pw, ph = tools.PAPER_PT[size]
                land = r.width > r.height if orient == "auto" else orient == "landscape"
                kinds.add((round(ph), round(pw)) if land else (round(pw), round(ph)))
            else:
                kinds.add((round(r.width), round(r.height)))
        if len(kinds) <= 1:
            return ", tất cả cùng khổ" + (f" {size} {'ngang' if next(iter(kinds))[0] > next(iter(kinds))[1] else 'dọc'}"
                                           if size and kinds else "")
        return f", CÓ {len(kinds)} KHỔ/HƯỚNG KHÁC NHAU"

    def _refresh(self):
        import pymupdf
        n_files = self.list.count()
        total = len(self.plan)
        self.ok_btn.setEnabled(total > 0 and not self.err and n_files >= 1)
        if total == 0:
            self.preview.show_text(self.err or ("Chưa có file nào.\nBấm “Thêm file…” hoặc kéo thả file vào cửa sổ này."
                                              if n_files == 0 else "Không có trang nào được chọn"))
            self.page_lb.setText("")
            self.summary.setText(self.err)
            self.b_prev.setEnabled(False)
            self.b_next.setEnabled(False)
            return
        self.page = max(0, min(self.page, total - 1))
        fid, src = self.plan[self.page]
        if fid not in self.docs:
            return
        doc = self.docs[fid]
        name = ""
        for i in range(n_files):
            if self.list.item(i).data(self.ID) == fid:
                name = os.path.basename(self.list.item(i).data(Qt.UserRole))
                break
        scaled = False
        try:
            from . import tools
            tmp = pymupdf.open()   # dựng đúng trang kết quả (đã co giãn nếu cần) rồi mới vẽ xem trước
            scaled = tools.add_page_resized(tmp, doc, src, self.size.currentData() or None, self.flat,
                                            self.orient.currentData())
            page = tmp[0]
            dpr = self.devicePixelRatioF()
            k = self.preview.scale(page.rect.width, page.rect.height)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(k * dpr, k * dpr), alpha=False)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
            p = QPainter(img)
            p.setPen(QColor("#9aa0a6"))
            p.drawRect(0, 0, img.width() - 1, img.height() - 1)
            p.end()
            pm = QPixmap.fromImage(img)
            pm.setDevicePixelRatio(dpr)
            self.preview.show_pixmap(pm)
            w_mm, h_mm = page.rect.width * 25.4 / 72, page.rect.height * 25.4 / 72
            size = f"{w_mm:.0f} × {h_mm:.0f} mm"
            if scaled:
                o = doc[src].rect
                size += f" (gốc {o.width * 25.4 / 72:.0f} × {o.height * 25.4 / 72:.0f} mm, đã co giãn)"
            tmp.close()
        except Exception as e:
            self.preview.show_text(f"Không hiển thị được trang này:\n{e}")
            size = ""
        self.page_lb.setText(f"Trang {self.page + 1} / {total}   ({name}, trang {src + 1})")
        self.b_prev.setEnabled(self.page > 0)
        self.b_next.setEnabled(self.page < total - 1)
        self.summary.setText(self.err or f"{n_files} file → PDF {total} trang{self._uniform_text()}.  "
                                         f"Trang đang xem: {size}")

    def accept(self):
        if not self.plan or self.err:
            return
        self.cfg["merge_size"] = self.size.currentData()
        self.cfg["merge_orient"] = self.orient.currentData()
        super().accept()

    def close_docs(self):
        self._timer.stop()
        self.plan = []
        for d in self.flat.values():
            try:
                d.close()
            except Exception:
                pass
        self.flat.clear()
        for d in self.docs.values():
            try:
                d.close()
            except Exception:
                pass
        self.docs.clear()


# ----------------------------------------------------------- tách file có xem trước
class SplitDialog(QDialog):
    """Chọn cách tách, xem danh sách file sẽ tạo và xem trước từng trang trước khi tách."""

    def __init__(self, parent, doc, base: str, current: int = 0, cfg: dict | None = None):
        super().__init__(parent)
        from PySide6.QtCore import QTimer
        self.setWindowTitle("Tách file PDF")
        fit_dialog(self, 1040, 700)
        self.doc = doc
        self.base = base
        self.cfg = cfg if cfg is not None else {}
        self.plan: list = []
        self.err = ""
        self.page_in_file = 0
        n = doc.page_count
        try:
            self.has_toc = bool(doc.get_toc(simple=True))
        except Exception:
            self.has_toc = False
        root = QHBoxLayout(self)
        left = QVBoxLayout()
        root.addLayout(left, 4)
        left.addWidget(_wrap_label(f"Tài liệu có <b>{n}</b> trang. Chọn cách tách:"))

        g = QGroupBox("Cách tách")
        gl = QVBoxLayout(g)
        self.r_ranges = QRadioButton("Theo khoảng trang / trích trang: mỗi khoảng thành một file")
        self.e_ranges = QLineEdit()
        self.e_ranges.setPlaceholderText("Ví dụ: 1-3, 4-10, 11-    ·    trích vài trang rời ra MỘT file: 1-3+7+12")
        self.r_at = QRadioButton("Cắt tại các trang: mỗi trang nêu ra bắt đầu một file mới")
        self.e_at = QLineEdit()
        self.e_at.setPlaceholderText(f"Ví dụ: {min(n, max(2, current + 1))}   hoặc   5, 12, 30")
        self.r_every = QRadioButton("Chia đều: cứ N trang một file")
        self.s_every = QSpinBox()
        self.s_every.setRange(1, max(1, n))
        self.s_every.setValue(min(max(1, n), 10 if n > 20 else 2))
        self.s_every.setSuffix(" trang mỗi file")
        self.r_toc = QRadioButton("Theo bookmark cấp 1: mỗi chương một file")
        self.r_toc.setEnabled(self.has_toc)
        if not self.has_toc:
            self.r_toc.setText("Theo bookmark (tài liệu này chưa có bookmark)")
        self.r_each = QRadioButton("Rời từng trang: mỗi trang một file")
        for r, w in ((self.r_ranges, self.e_ranges), (self.r_at, self.e_at), (self.r_every, self.s_every),
                     (self.r_toc, None), (self.r_each, None)):
            gl.addWidget(r)
            if w is not None:
                row = QHBoxLayout()
                row.setContentsMargins(24, 0, 0, 4)
                row.addWidget(w)
                gl.addLayout(row)
            r.toggled.connect(self._changed)
        left.addWidget(g)

        self.result_lb = QLabel("")
        self.result_lb.setWordWrap(True)
        left.addWidget(self.result_lb)
        self.list = QListWidget()
        self.list.setMinimumWidth(240)
        self.list.currentRowChanged.connect(self._file_selected)
        left.addWidget(self.list, 1)
        bb = _buttons(self, "Tách và chọn thư mục lưu…")
        self.ok_btn = bb.button(QDialogButtonBox.Ok)
        left.addWidget(bb)

        right = QVBoxLayout()
        root.addLayout(right, 5)
        self.preview = PreviewBox()
        self.preview.step.connect(self._step)
        self.preview.changed.connect(lambda: self._timer.start())
        right.addWidget(self.preview, 1)
        nav = QHBoxLayout()
        self.b_prev = QPushButton("◀ Trang trước")
        self.b_next = QPushButton("Trang sau ▶")
        self.page_lb = QLabel("")
        self.page_lb.setAlignment(Qt.AlignCenter)
        self.b_prev.clicked.connect(lambda: self._step(-1))
        self.b_next.clicked.connect(lambda: self._step(1))
        nav.addWidget(self.b_prev)
        nav.addWidget(self.page_lb, 1)
        nav.addWidget(self.b_next)
        right.addLayout(nav)

        self._timer = QTimer(self, singleShot=True, interval=90, timeout=self._refresh)
        self._plan_timer = QTimer(self, singleShot=True, interval=200, timeout=self._rebuild)
        self.e_ranges.textChanged.connect(lambda: self._plan_timer.start())
        self.e_at.textChanged.connect(lambda: self._plan_timer.start())
        self.s_every.valueChanged.connect(lambda: self._plan_timer.start())
        last = self.cfg.get("split_mode", "ranges")
        {"ranges": self.r_ranges, "at": self.r_at, "every": self.r_every, "each": self.r_each,
         "toc": self.r_toc if self.has_toc else self.r_ranges}.get(last, self.r_ranges).setChecked(True)
        self._changed()

    # ------------------------------------------------------------ kế hoạch tách
    def mode(self) -> tuple[str, object]:
        if self.r_ranges.isChecked():
            return "ranges", self.e_ranges.text()
        if self.r_at.isChecked():
            return "at", self.e_at.text()
        if self.r_every.isChecked():
            return "every", self.s_every.value()
        if self.r_toc.isChecked():
            return "toc", 1
        return "each", ""

    def _changed(self, *_):
        self.e_ranges.setEnabled(self.r_ranges.isChecked())
        self.e_at.setEnabled(self.r_at.isChecked())
        self.s_every.setEnabled(self.r_every.isChecked())
        if self.r_ranges.isChecked():
            self.e_ranges.setFocus()
        elif self.r_at.isChecked():
            self.e_at.setFocus()
        self._rebuild()

    def _rebuild(self):
        from . import tools
        mode, value = self.mode()
        self.err = ""
        try:
            self.plan = tools.split_plan(self.doc, mode, value)
        except tools.PdfError as e:
            self.plan, self.err = [], str(e)
        except Exception as e:
            self.plan, self.err = [], f"{e}"
        self.list.blockSignals(True)
        self.list.clear()
        names = tools.split_filenames(self.plan, self.base) if self.plan else []
        for (label, pages), name in zip(self.plan[:2000], names):
            it = QListWidgetItem(f"{name}\n{len(pages)} trang: {tools._pages_label(pages)}")
            self.list.addItem(it)
        self.list.blockSignals(False)
        n = self.doc.page_count
        if self.err:
            typing = mode in ("ranges", "at") and not str(value).strip()
            self.result_lb.setText(f"<span style='color:{'#5f6368' if typing else '#d93025'}'>{self.err}</span>")
        else:
            used = set()
            for _l, pages in self.plan:
                used.update(pages)
            parts = [f"Sẽ tạo <b>{len(self.plan)}</b> file:"]
            missing = n - len(used)
            if missing:
                parts.append(f"<span style='color:#b06000'>({missing} trang không nằm trong khoảng nào nên sẽ "
                             f"không có trong các file tách)</span>")
            if len(self.plan) > 100:
                parts.append("<span style='color:#b06000'>Số file khá nhiều, hãy chắc là bro muốn vậy.</span>")
            if len(self.plan) == 1 and len(used) == n:
                parts.append("<span style='color:#b06000'>Kết quả giống hệt file gốc, chưa tách gì.</span>")
            self.result_lb.setText(" ".join(parts))
        self.ok_btn.setEnabled(bool(self.plan) and not self.err)
        self.page_in_file = 0
        if self.plan:
            self.list.setCurrentRow(0)
        self._timer.start()

    def _file_selected(self, _row: int):
        self.page_in_file = 0
        self._timer.start()

    def _step(self, d: int):
        """Sang trang sau/trước; hết file này thì nhảy sang file kế tiếp trong danh sách."""
        if not self.plan:
            return
        r = max(0, self.list.currentRow())
        pages = self.plan[r][1]
        k = self.page_in_file + d
        if k < 0:
            if r > 0:
                self.list.blockSignals(True)
                self.list.setCurrentRow(r - 1)
                self.list.blockSignals(False)
                self.page_in_file = len(self.plan[r - 1][1]) - 1
        elif k >= len(pages):
            if r < len(self.plan) - 1 and r + 1 < self.list.count():
                self.list.blockSignals(True)
                self.list.setCurrentRow(r + 1)
                self.list.blockSignals(False)
                self.page_in_file = 0
        else:
            self.page_in_file = k
        self._refresh()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._timer.start()

    def _refresh(self):
        import pymupdf
        if not self.plan:
            self.preview.show_text(self.err or "Chưa có file nào để xem trước")
            self.page_lb.setText("")
            self.b_prev.setEnabled(False)
            self.b_next.setEnabled(False)
            return
        r = max(0, min(self.list.currentRow(), len(self.plan) - 1))
        pages = self.plan[r][1]
        self.page_in_file = max(0, min(self.page_in_file, len(pages) - 1))
        pno = pages[self.page_in_file]
        try:
            page = self.doc[pno]
            dpr = self.devicePixelRatioF()
            k = self.preview.scale(page.rect.width, page.rect.height)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(k * dpr, k * dpr), alpha=False)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
            p = QPainter(img)
            p.setPen(QColor("#9aa0a6"))
            p.drawRect(0, 0, img.width() - 1, img.height() - 1)
            p.end()
            pm = QPixmap.fromImage(img)
            pm.setDevicePixelRatio(dpr)
            self.preview.show_pixmap(pm)
        except Exception as e:
            self.preview.show_text(f"Không hiển thị được trang này:\n{e}")
        self.page_lb.setText(f"File {r + 1} / {len(self.plan)} · trang {self.page_in_file + 1} / {len(pages)} "
                             f"(trang {pno + 1} của file gốc)")
        self.b_prev.setEnabled(r > 0 or self.page_in_file > 0)
        self.b_next.setEnabled(r < len(self.plan) - 1 or self.page_in_file < len(pages) - 1)

    def accept(self):
        if not self.plan or self.err:
            return
        self.cfg["split_mode"] = self.mode()[0]
        super().accept()


# ----------------------------------------------------------- dịch tài liệu
class TranslateDialog(QDialog):
    """Chọn bộ máy dịch, ngôn ngữ đích, lĩnh vực chuyên ngành và phạm vi trang."""

    def __init__(self, parent, cfg: dict, n_pages: int, current: int = 0):
        super().__init__(parent)
        from . import translate as T
        self.T = T
        self.cfg = cfg
        self.n = n_pages
        self._local_done = False
        self.setWindowTitle("Dịch tài liệu sang ngôn ngữ khác")
        self.setMinimumWidth(600)
        saved = cfg.get("translate", {})
        # nội dung nằm trong khung cuộn: màn hình thấp (hoặc tỉ lệ hiển thị 125–150%) vẫn xem được hết, nút bấm luôn hiện
        outer = QVBoxLayout(self)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.body = QWidget()
        lay = QVBoxLayout(self.body)
        lay.setContentsMargins(0, 0, 6, 0)
        self.scroll.setWidget(self.body)
        outer.addWidget(self.scroll, 1)

        g = QGroupBox("Bộ máy dịch")
        gl = QFormLayout(g)
        self.engine = QComboBox()
        self.engine.addItem("Gemini của Google (AI, có gói miễn phí, cần API key)", "gemini")
        self.engine.addItem("Google Translate (miễn phí, không cần key, chất lượng thông thường)", "google")
        self.engine.addItem("AI khác theo chuẩn OpenAI (OpenAI, OpenRouter, Ollama chạy trên máy…)", "openai")
        # chưa từng cấu hình và chưa có key: mặc định Google Translate để bấm Dịch là chạy được ngay
        first = "gemini" if (cfg.get("gemini_key") or T.env_keys()["gemini"]) else "google"
        self.engine.setCurrentIndex(max(0, self.engine.findData(saved.get("engine", first))))
        gl.addRow("Dùng:", self.engine)
        self.gem_key = QLineEdit(cfg.get("gemini_key", ""))
        self.gem_key.setEchoMode(QLineEdit.Password)
        self.gem_key.setPlaceholderText("Dán API key vào đây")
        self.gem_model = QLineEdit(cfg.get("gemini_model", ""))
        self.gem_model.setPlaceholderText("Để trống = tự chọn model Flash mới nhất mà key dùng được")
        self.gem_help = QLabel('Chỉ cần làm một lần: bấm “Lấy key…”, đăng nhập tài khoản Google, bấm “Create API key”, '
                               'sao chép rồi bấm “Dán”. App sẽ nhớ key cho những lần sau. Ô Model cứ để trống.')
        self.gem_help.setOpenExternalLinks(True)
        self.gem_help.setWordWrap(True)
        self.oa_base = QLineEdit(cfg.get("openai_base", ""))
        self.oa_base.setPlaceholderText("https://api.openai.com/v1   (Ollama: http://localhost:11434/v1)")
        self.oa_key = QLineEdit(cfg.get("openai_key", ""))
        self.oa_key.setEchoMode(QLineEdit.Password)
        self.oa_key.setPlaceholderText("API key (AI chạy trên máy thì để trống)")
        self.oa_model = QLineEdit(cfg.get("openai_model", ""))
        self.oa_model.setPlaceholderText("Tên model, ví dụ gpt-4o-mini hoặc qwen2.5:14b")
        env = T.env_keys()
        self.env_note = ""
        if not self.gem_key.text() and env["gemini"]:
            self.gem_key.setText(env["gemini"])
            self.env_note = "Đã lấy API key Gemini từ biến môi trường của máy này."
        if not self.oa_key.text() and env["openai"]:
            self.oa_key.setText(env["openai"])

        def row_of(*widgets):
            w = QWidget()
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            for x in widgets:
                h.addWidget(x, 1 if isinstance(x, (QLineEdit, QComboBox)) else 0)
            return w

        def btn(text, fn, tip=""):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            return b

        gem_key_row = row_of(self.gem_key,
                             btn("Lấy key…", lambda: self._open_url("https://aistudio.google.com/apikey"),
                                 "Mở trang tạo API key miễn phí của Google trong trình duyệt"),
                             btn("Dán", lambda: self._paste(self.gem_key), "Dán key vừa sao chép"),
                             btn("Kiểm tra", self._check_gemini, "Thử key và xem app sẽ dùng model nào"))
        self.oa_server = QComboBox()
        self.oa_server.addItem("Tự nhập địa chỉ", "")
        for name, base, _need, _url in T.SERVERS:
            self.oa_server.addItem(name, base)
        self.oa_server.setCurrentIndex(max(0, self.oa_server.findData(self.oa_base.text().strip())))
        self.oa_server.currentIndexChanged.connect(self._server_picked)
        self.oa_models = QComboBox()
        self.oa_models.setEditable(True)
        self.oa_models.setLineEdit(self.oa_model)
        oa_key_row = row_of(self.oa_key, btn("Lấy key…", self._open_key_page, "Mở trang lấy API key của máy chủ đang chọn"),
                            btn("Dán", lambda: self._paste(self.oa_key)))
        oa_model_row = row_of(self.oa_models, btn("Tìm model", self._find_models,
                                                  "Hỏi máy chủ danh sách model rồi điền vào ô này"))
        self.oa_status = QLabel("")
        self.oa_status.setWordWrap(True)
        self.oa_status.setStyleSheet("color:#3c4043")
        self.gem_status = QLabel(self.env_note)
        self.gem_status.setWordWrap(True)
        self.gem_status.setStyleSheet("color:#188038")
        self.gem_fast = QCheckBox("Ưu tiên tốc độ: model chính hết lượt thì dùng tạm model khác thay vì chờ")
        self.gem_fast.setToolTip("Gói miễn phí giới hạn số lượt gọi mỗi phút cho TỪNG model. Bật mục này thì app luân phiên "
                                 "nhiều model để khỏi chờ; đổi lại các phần của tài liệu có thể do model khác nhau dịch, "
                                 "thuật ngữ kém đồng đều hơn một chút.")
        self.gem_fast.setChecked(bool(cfg.get("gemini_fast", False)))
        self.rows = {"gemini": [("API key:", gem_key_row), ("Model:", self.gem_model), ("", self.gem_fast),
                                ("", self.gem_status),
                                ("", self.gem_help)],
                     "openai": [("Máy chủ:", self.oa_server), ("Địa chỉ máy chủ:", self.oa_base),
                                ("API key:", oa_key_row), ("Model:", oa_model_row), ("", self.oa_status)]}
        self.row_labels = []
        for kind, rows in self.rows.items():
            for label, w in rows:
                lb = QLabel(label)
                gl.addRow(lb, w)
                self.row_labels.append((kind, lb, w))
        self.privacy = QLabel("")
        self.privacy.setWordWrap(True)
        self.privacy.setStyleSheet("color:#b06000")
        gl.addRow("", self.privacy)
        lay.addWidget(g)

        g = QGroupBox("Nội dung dịch")
        fl = QFormLayout(g)
        self.target = QComboBox()
        self.target.setEditable(True)
        for code, vi, _en in T.LANGS:
            self.target.addItem(vi, code)
        want = saved.get("target", "en")
        i = self.target.findData(want)
        if i >= 0:
            self.target.setCurrentIndex(i)
        else:
            self.target.setEditText(want)
        self.target.lineEdit().setPlaceholderText("Chọn hoặc gõ tên ngôn ngữ bất kỳ")
        fl.addRow("Dịch sang:", self.target)
        self.source = QComboBox()
        self.source.addItem("Tự nhận diện", "")
        for code, vi, _en in T.LANGS:
            self.source.addItem(vi, code)
        fl.addRow("Ngôn ngữ gốc:", self.source)
        self.domain = QComboBox()
        for key, vi, _en in T.DOMAINS:
            self.domain.addItem(vi, key)
        self.domain.setCurrentIndex(max(0, self.domain.findData(saved.get("domain", "general"))))
        fl.addRow("Lĩnh vực chuyên ngành:", self.domain)
        self.glossary = QPlainTextEdit(saved.get("glossary", ""))
        self.glossary.setPlaceholderText("Tuỳ chọn. Mỗi dòng một thuật ngữ bắt buộc, dạng:  từ gốc = từ dịch\n"
                                         "Ví dụ:  Bên A = Party A")
        self.glossary.setMaximumHeight(54)
        fl.addRow("Bảng thuật ngữ:", self.glossary)
        self.pages = QLineEdit()
        self.pages.setPlaceholderText(f"Để trống = cả {n_pages} trang. Ví dụ: 1-3, 5   (trang đang xem: {current + 1})")
        fl.addRow("Trang cần dịch:", self.pages)
        self.toc = QCheckBox("Dịch cả tên bookmark")
        self.toc.setChecked(saved.get("toc", True))
        fl.addRow("", self.toc)
        self.img_on = QCheckBox("Dịch cả chữ nằm trong hình ảnh (chậm hơn, tốn thêm lượt gọi)")
        self.img_on.setToolTip("Chữ nằm trong ảnh chụp màn hình, sơ đồ… được đọc bằng OCR, dịch rồi viết đè lên hình.\n"
                               "Chữ quá mờ, quá nhỏ không đọc chắc được thì giữ nguyên.\n"
                               "Mặc định TẮT vì tài liệu nhiều hình sẽ dịch lâu hơn nhiều và tốn thêm lượt gọi Gemini.")
        self.img_on.setChecked(bool(saved.get("images_on", False)))
        self.images = QComboBox()
        for key, name in (("auto", "Tự chọn bộ máy đọc chữ"), ("gemini", "Đọc bằng Gemini"),
                          ("rapid", "Đọc bằng RapidOCR (trên máy)"), ("tesseract", "Đọc bằng Tesseract (trên máy)")):
            self.images.addItem(name, key)
        self.images.setCurrentIndex(max(0, self.images.findData(saved.get("images", "auto"))))
        self.images.setToolTip("Tự chọn: dùng Gemini nếu đang dịch bằng Gemini; không thì RapidOCR hoặc Tesseract trên máy.")
        fl.addRow("", self.img_on)
        fl.addRow("Đọc chữ trong hình:", self.images)
        fl.setRowVisible(self.images, self.img_on.isChecked())      # chỉ hiện ô chọn bộ máy đọc khi có tích
        self.img_on.toggled.connect(lambda on: (fl.setRowVisible(self.images, on), self._relayout()))
        from . import tm
        self.mem = tm.memory(data_dir())
        self.use_tm = QCheckBox("Dùng bộ nhớ dịch (câu đã dịch được lấy lại ngay)")
        self.use_tm.setToolTip("Mỗi câu đã dịch (và câu bro tự sửa trong bảng rà soát) được lưu trên máy này.\n"
                               "Dịch lại cùng tài liệu sẽ gần như tức thì và giữ đúng những chỗ đã sửa.\n"
                               "Bỏ tích nếu muốn máy dịch lại toàn bộ từ đầu (ví dụ sau khi đổi lĩnh vực hoặc bảng thuật ngữ).")
        self.use_tm.setChecked(saved.get("tm", True))
        self.tm_lb = QLabel()
        self.tm_lb.setStyleSheet("color:#5f6368")
        tm_clear = QPushButton("Xoá bộ nhớ…")
        tm_clear.clicked.connect(self._clear_tm)
        tm_row = QHBoxLayout()
        tm_row.addWidget(self.tm_lb, 1)
        tm_row.addWidget(tm_clear)
        fl.addRow("", self.use_tm)
        fl.addRow("", tm_row)
        self._tm_count()
        lay.addWidget(g)

        note = QLabel("Bản dịch mở ở tab mới, file gốc giữ nguyên; bố cục, hình ảnh, header/footer không đổi. "
                      "Bản scan / ảnh chụp: tích ô “Dịch cả chữ nằm trong hình ảnh”. Máy dịch có thể sai: văn bản quan trọng nên có người rà lại.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#5f6368")
        lay.addWidget(note)
        self.bb = _buttons(self, "Dịch")
        outer.addWidget(self.bb)
        # nhãn nhiều dòng trong bảng nhập dễ bị bóp chiều cao: đặt sẵn chiều cao tối thiểu theo số dòng
        ls = self.fontMetrics().lineSpacing()
        self.privacy.setMinimumHeight(ls * 3 + 2)
        self.gem_help.setMinimumHeight(ls * 3 + 2)
        self.gem_status.setMinimumHeight(ls + 2)
        self.gem_status.setTextInteractionFlags(Qt.TextSelectableByMouse)   # để sao chép được nguyên văn lỗi
        self.oa_status.setMinimumHeight(ls * 2 + 2)
        for lb in (self.privacy, self.gem_help, self.gem_status, self.oa_status):
            lb.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.engine.currentIndexChanged.connect(self._engine_changed)
        self._engine_changed()

    def _recenter(self):
        ls = self.fontMetrics().lineSpacing()
        for lb in (self.gem_status, self.oa_status):   # dòng trạng thái dài nhiều dòng: cho đủ chiều cao để không bị cắt
            if lb.isVisible():
                lb.setMinimumHeight(max(ls + 2, lb.heightForWidth(max(240, lb.width())) + 2))
        from PySide6.QtGui import QGuiApplication
        m = self.layout().contentsMargins()
        want = self.body.sizeHint().height() + self.bb.sizeHint().height() + m.top() + m.bottom() + self.layout().spacing() + 6
        parent = self.parentWidget()
        screen = (parent.screen() if parent is not None else None) or QGuiApplication.primaryScreen()
        room = screen.availableGeometry().height() - 80 if screen is not None else 700
        self.resize(max(self.width(), 620), max(260, min(want, room)))   # cao vừa nội dung, nhưng không vượt màn hình
        center_on_parent(self)

    def _relayout(self):
        """Nội dung đổi làm hộp thoại đổi cỡ: giãn lại rồi đưa về giữa cửa sổ app."""
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._recenter)

    def showEvent(self, e):
        super().showEvent(e)
        center_on_parent(self)
        self._relayout()

    # -- trợ giúp điền nhanh
    def _open_url(self, url: str):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl(url))

    def _paste(self, edit: QLineEdit):
        from PySide6.QtGui import QGuiApplication
        t = QGuiApplication.clipboard().text().strip()
        if t:
            edit.setText(t.split()[0])

    def _busy(self, fn):
        from PySide6.QtWidgets import QApplication
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        try:
            return fn(), ""
        except self.T.TranslateError as e:
            return None, str(e)
        except Exception as e:
            return None, f"{type(e).__name__}: {e}"
        finally:
            while QApplication.overrideCursor():
                QApplication.restoreOverrideCursor()

    def _check_gemini(self):
        """Thử key ở luồng riêng (cửa sổ không bị đơ), có nút Dừng và tự bỏ cuộc sau 60 giây."""
        import threading
        from PySide6.QtCore import QEventLoop, QTimer
        from PySide6.QtWidgets import QProgressDialog
        key = self.gem_key.text().strip()
        if not key:
            self.gem_status.setStyleSheet("color:#d93025")
            self.gem_status.setText("Chưa có key. Bấm “Lấy key…” để tạo key miễn phí.")
            self._relayout()
            return
        T = self.T
        box: dict = {}
        holder: list = []
        fixed = self.gem_model.text().strip()

        def work():
            try:
                prefer = getattr(self, "_good_model", "") or \
                    (self.cfg.get("gemini_prefer", "") if self.cfg.get("gemini_key", "") == key else "")
                box["res"] = T.check_gemini(key, holder, fixed, status=lambda t: box.__setitem__("step", t),
                                            prefer=prefer)
            except T.Cancelled:
                box["err"] = "Đã dừng kiểm tra."
            except T.TranslateError as e:
                box["err"] = str(e)
            except Exception as e:
                box["err"] = f"{type(e).__name__}: {e}"

        th = threading.Thread(target=work, daemon=True)
        prog = QProgressDialog("Đang hỏi máy chủ Google để kiểm tra key…", "Dừng", 0, 0, self)
        prog.setWindowTitle("Kiểm tra API key")
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)
        loop = QEventLoop()
        waited = {"ms": 0}

        def tick():
            waited["ms"] += 150
            if box.get("step"):
                prog.setLabelText(box["step"] + f"\n(đã chờ {waited['ms'] // 1000} giây)")
            if not th.is_alive() or prog.wasCanceled() or waited["ms"] > 200000:
                loop.quit()
        timer = QTimer(self, interval=150, timeout=tick)
        th.start()
        timer.start()
        prog.show()
        loop.exec()
        timer.stop()
        for e in holder:
            e.cancel = True
        stopped = prog.wasCanceled()
        prog.close()
        if th.is_alive() and "res" not in box and "err" not in box:
            box["err"] = "Đã dừng kiểm tra." if stopped else "Quá thời gian chờ, đã dừng kiểm tra."
        res = box.get("res")
        detail = "\n\n".join(res["lines"]) if res else box.get("err", "")
        if res and res["ok"]:
            color, head, icon_ = "#188038", f"Key dùng được. App sẽ dịch bằng model {res['model']}.", QMessageBox.Information
            if not fixed:
                self._good_model = res["model"]
        elif res and res["key_ok"]:
            color, head, icon_ = "#b06000", "Key hợp lệ, nhưng dịch thử chưa được (xem chi tiết).", QMessageBox.Warning
        else:
            color, head, icon_ = "#d93025", "Key chưa dùng được (xem chi tiết).", QMessageBox.Warning
        self.gem_status.setStyleSheet(f"color:{color}")
        self.gem_status.setText(head)     # dòng trạng thái chỉ một dòng; chi tiết hiện ở hộp riêng, sao chép được
        self._relayout()
        if detail and not (stopped and not res):
            mb = QMessageBox(icon_, "Kết quả kiểm tra API key", head, QMessageBox.Ok, self)
            mb.setInformativeText(detail)
            mb.setTextInteractionFlags(Qt.TextSelectableByMouse)
            mb.exec()

    def _server_picked(self, *_):
        base = self.oa_server.currentData()
        if base:
            self.oa_base.setText(base)
        need = next((n for _nm, b, n, _u in self.T.SERVERS if b == base), True)
        self.oa_key.setEnabled(need)
        self.oa_key.setPlaceholderText("API key" if need else "Không cần key")
        if base and not need:
            self._find_models(quiet=True)

    def _open_key_page(self):
        base = self.oa_base.text().strip().rstrip("/")
        url = next((u for _nm, b, _n, u in self.T.SERVERS if b.rstrip("/") == base), "")
        if url:
            self._open_url(url)
        else:
            self.oa_status.setText("Không rõ trang lấy key của máy chủ này; hãy xem hướng dẫn của nhà cung cấp.")
            self._relayout()

    def _find_models(self, *_a, quiet: bool = False):
        base = self.oa_base.text().strip() or "https://api.openai.com/v1"
        models, err = self._busy(lambda: self.T.list_models(base, self.oa_key.text()))
        if err:
            self.oa_status.setStyleSheet("color:#d93025")
            local = "localhost" in base or "127.0.0.1" in base
            self.oa_status.setText(("Chưa thấy AI nào đang chạy ở địa chỉ này. Hãy cài và mở Ollama hoặc LM Studio trước."
                                    if local else err.split("\n")[0]))
            return
        cur = self.oa_model.text().strip()
        self.oa_models.blockSignals(True)
        self.oa_models.clear()
        self.oa_models.addItems(models)
        self.oa_models.blockSignals(False)
        if cur and cur in models:
            self.oa_models.setCurrentText(cur)
        elif models:
            self.oa_models.setCurrentIndex(0)
        self.oa_status.setStyleSheet("color:#188038" if models else "color:#b06000")
        self.oa_status.setText(f"Tìm thấy {len(models)} model, đã điền sẵn vào ô Model (bấm mũi tên để chọn model khác)."
                               if models else "Máy chủ chưa có model nào. Với Ollama: tải một model trước, ví dụ "
                                              "“ollama pull qwen2.5:7b”.")
        self._relayout()

    def _auto_local(self):
        """Lần đầu chọn mục AI khác mà chưa khai báo gì: tự dò AI đang chạy trên máy và điền sẵn."""
        if self._local_done or self.oa_base.text().strip() or self.oa_model.text().strip():
            return
        self._local_done = True
        found, _err = self._busy(self.T.detect_local)
        if found:
            name, base, models = found[0]
            self.oa_server.setCurrentIndex(max(0, self.oa_server.findData(base)))
            self.oa_base.setText(base)
            if models:
                self.oa_models.clear()
                self.oa_models.addItems(models)
                self.oa_models.setCurrentIndex(0)
            self.oa_status.setStyleSheet("color:#188038")
            self.oa_status.setText(f"Đã tự tìm thấy {name} với {len(models)} model và điền sẵn.")
            self._relayout()
        else:
            self.oa_status.setStyleSheet("color:#5f6368")
            self.oa_status.setText("Chưa thấy AI nào chạy trên máy này. Chọn một máy chủ ở trên, hoặc cài Ollama để "
                                   "dịch miễn phí, không cần key và không gửi nội dung ra ngoài.")
            self._relayout()

    def _engine_changed(self, *_):
        kind = self.engine.currentData()
        if kind == "openai":
            self._auto_local()
        for k, lb, w in self.row_labels:
            lb.setVisible(k == kind)
            w.setVisible(k == kind)
        ai = kind != "google"
        self.domain.setEnabled(ai)
        self.glossary.setEnabled(ai)
        self.privacy.setText({
            "gemini": "Nội dung trang được gửi lên máy chủ Google. Với gói miễn phí, Google ghi rõ nội dung được dùng để "
                      "cải thiện sản phẩm của họ: không nên dùng cho tài liệu mật.",
            "google": "Nội dung trang được gửi lên Google Translate. Không chọn được lĩnh vực hay bảng thuật ngữ; "
                      "chất lượng ở mức thông thường, không đạt chuẩn chuyên ngành.",
            "openai": "Nội dung trang được gửi tới máy chủ bro khai báo. Nếu đó là AI chạy ngay trên máy (Ollama, "
                      "LM Studio) thì nội dung không rời khỏi máy."}[kind])
        self._relayout()

    def _tm_count(self):
        try:
            n = self.mem.count()
        except Exception:
            n = 0
        self.tm_lb.setText(f"Bộ nhớ dịch: {n} câu, lưu trên máy này")

    def _clear_tm(self):
        if QMessageBox.question(self, "Dịch", "Xoá toàn bộ các câu đã lưu trong bộ nhớ dịch (kể cả câu bro đã tự sửa)?") \
                == QMessageBox.Yes:
            self.mem.clear()
            self._tm_count()

    def options(self) -> dict:
        t = self.target.currentText().strip()
        i = self.target.findText(t)
        target = self.target.itemData(i) if i >= 0 else t
        return {"engine": self.engine.currentData(), "target": target, "source": self.source.currentData(),
                "domain": self.domain.currentData(), "glossary": self.glossary.toPlainText(),
                "pages": self.pages.text(), "toc": self.toc.isChecked(), "tm": self.use_tm.isChecked(),
                "images": self.images.currentData() if self.img_on.isChecked() else "off"}

    def accept(self):
        from . import tools
        o = self.options()
        if not o["target"]:
            QMessageBox.warning(self, "Dịch", "Hãy chọn ngôn ngữ muốn dịch sang.")
            return
        try:
            tools.parse_ranges(o["pages"], self.n)
        except tools.PdfError as e:
            QMessageBox.warning(self, "Dịch", str(e))
            return
        if o["engine"] == "gemini" and not self.gem_key.text().strip():
            QMessageBox.warning(self, "Dịch", "Chưa có API key của Gemini.\n\nLấy key miễn phí tại aistudio.google.com/apikey "
                                "rồi dán vào ô API key, hoặc chọn Google Translate để dịch không cần key.")
            return
        if o["engine"] == "openai" and not self.oa_model.text().strip():
            QMessageBox.warning(self, "Dịch", "Hãy nhập tên model.")
            return
        c = self.cfg
        if c.get("gemini_key", "") != self.gem_key.text().strip():
            c.pop("gemini_prefer", None)          # đổi key thì bỏ ghi nhớ model của key cũ
        if getattr(self, "_good_model", ""):
            c["gemini_prefer"] = self._good_model
        c["gemini_key"], c["gemini_model"] = self.gem_key.text().strip(), self.gem_model.text().strip()
        c["gemini_fast"] = self.gem_fast.isChecked()
        c["openai_base"], c["openai_key"] = self.oa_base.text().strip(), self.oa_key.text().strip()
        c["openai_model"] = self.oa_model.text().strip()
        c["translate"] = {"engine": o["engine"], "target": o["target"], "domain": o["domain"],
                          "glossary": o["glossary"], "toc": o["toc"], "tm": o["tm"],
                          "images_on": self.img_on.isChecked(), "images": self.images.currentData()}
        super().accept()


class ReviewDialog(QDialog):
    """Bảng rà soát: câu gốc bên trái, câu dịch bên phải (sửa được). Trả về các câu dịch sau khi sửa."""

    def __init__(self, parent, page_no: int, pairs: list[tuple[str, str]]):
        super().__init__(parent)
        from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem
        self.setWindowTitle(f"Rà soát câu dịch – trang {page_no}")
        lay = QVBoxLayout(self)
        tip = QLabel("Bấm đúp vào ô <b>Bản dịch</b> để sửa. Bấm <b>Áp dụng</b> thì trang được dựng lại từ bản gốc với các câu "
                     "đã sửa, giữ nguyên bố cục. Dấu &lt;g1&gt;…&lt;/g1&gt; bao quanh cụm chữ đậm / gạch dưới / liên kết: "
                     "giữ nguyên dấu, chỉ sửa chữ bên trong.")
        tip.setWordWrap(True)
        tip.setMinimumHeight(tip.fontMetrics().lineSpacing() * 3)
        lay.addWidget(tip)
        self.table = QTableWidget(len(pairs), 2)
        self.table.setHorizontalHeaderLabels(["Bản gốc", "Bản dịch (sửa được)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setWordWrap(True)
        self.table.setAlternatingRowColors(True)
        for r, (src, dst) in enumerate(pairs):
            a = QTableWidgetItem(src)
            a.setFlags(a.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(r, 0, a)
            self.table.setItem(r, 1, QTableWidgetItem(dst))
        self.before = [d for _s, d in pairs]
        lay.addWidget(self.table, 1)
        self.save_tm = QCheckBox("Lưu các câu đã sửa vào bộ nhớ dịch (lần sau dịch lại sẽ dùng đúng câu này)")
        self.save_tm.setChecked(True)
        lay.addWidget(self.save_tm)
        bb = QDialogButtonBox()
        bb.addButton("Áp dụng", QDialogButtonBox.AcceptRole)
        bb.addButton("Đóng", QDialogButtonBox.RejectRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        fit_dialog(self, 980, 640)
        center_on_parent(self)

    def accept(self):
        self.table.setCurrentItem(None)      # chốt ô đang gõ dở
        super().accept()

    def result_texts(self) -> list[str]:
        return [" ".join(self.table.item(r, 1).text().split()) for r in range(self.table.rowCount())]

    def changed_rows(self) -> list[int]:
        new = self.result_texts()
        return [r for r in range(len(new)) if new[r] != " ".join(self.before[r].split())]


class OcrDialog(QDialog):
    """Chọn bộ máy nhận dạng chữ: Tesseract, RapidOCR (trên máy) hoặc Gemini (trên mạng)."""

    def __init__(self, parent, cfg: Config, tess_langs: list[str], rapid_ok: bool, install_rapid=None):
        super().__init__(parent)
        from . import ocr
        self.cfg, self.tess_langs, self.rapid_ok, self.install_rapid = cfg, tess_langs, rapid_ok, install_rapid
        self.setWindowTitle("Nhận dạng chữ (OCR)")
        saved = cfg.get("ocr", {})
        lay = QVBoxLayout(self)
        fl = QFormLayout()
        self.engine = QComboBox()
        have = {"tesseract": bool(tess_langs), "rapid": rapid_ok, "gemini": bool(cfg.get("gemini_key"))}
        missing = {"tesseract": "  (chưa cài)", "rapid": "  (chưa cài)", "gemini": "  (chưa có API key)"}
        for key, name in (("tesseract", "Tesseract – trên máy, nhẹ, hợp bản scan sạch"),
                          ("rapid", "RapidOCR – trên máy, tốt hơn với ảnh chụp / scan xấu"),
                          ("gemini", "Gemini – trên mạng, chính xác nhất với tài liệu khó")):
            self.engine.addItem(name + ("" if have[key] else missing[key]), key)
        fl.addRow("Bộ máy:", self.engine)
        self.lang = QComboBox()
        fl.addRow("Ngôn ngữ:", self.lang)
        self.dpi = QSpinBox()
        self.dpi.setRange(150, 600)
        self.dpi.setSingleStep(50)
        self.dpi.setValue(int(saved.get("dpi", 300)))
        fl.addRow("Độ phân giải quét:", self.dpi)
        self.only = QCheckBox("Chỉ nhận dạng các trang chưa có chữ (trang đã chọn được chữ thì giữ nguyên)")
        self.only.setChecked(saved.get("only_scans", True))
        fl.addRow("", self.only)
        lay.addLayout(fl)
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setMinimumHeight(self.note.fontMetrics().lineSpacing() * 5)
        self.note.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.note.setStyleSheet("color:#5f6368")
        lay.addWidget(self.note)
        row = QHBoxLayout()
        self.b_install = QPushButton("Cài RapidOCR vào app (tải khoảng 100 MB)…")
        self.b_install.clicked.connect(self._install)
        row.addWidget(self.b_install)
        row.addStretch(1)
        bb = QDialogButtonBox()
        self.b_ok = bb.addButton("Nhận dạng", QDialogButtonBox.AcceptRole)
        bb.addButton("Huỷ", QDialogButtonBox.RejectRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        row.addWidget(bb)
        lay.addLayout(row)
        self._rapid_langs = ocr.RAPID_LANGS
        self.engine.currentIndexChanged.connect(self._engine_changed)
        want = saved.get("engine") or "tesseract"
        if not have.get(want):      # bộ máy đã chọn lần trước (hoặc mặc định) chưa dùng được: chọn sẵn bộ máy đang dùng được
            want = next((k for k in ("gemini", "rapid", "tesseract") if have[k]), want)
        self.engine.setCurrentIndex(max(0, self.engine.findData(want)))
        self._engine_changed()
        fit_dialog(self, 600, 330)
        center_on_parent(self)

    def _engine_changed(self, *_):
        kind = self.engine.currentData()
        saved = self.cfg.get("ocr", {})
        self.lang.clear()
        self.lang.setEnabled(True)
        ok = True
        if kind == "tesseract":
            if "vie" in self.tess_langs and "eng" in self.tess_langs:
                self.lang.addItem("Tiếng Việt + Tiếng Anh", "vie+eng")
            for l in self.tess_langs:
                self.lang.addItem({"vie": "Tiếng Việt", "eng": "Tiếng Anh"}.get(l, l), l)
            ok = bool(self.tess_langs)
            if not ok:
                self.lang.addItem("(chưa cài Tesseract nên chưa có ngôn ngữ nào)", "")
                self.lang.setEnabled(False)
            note = "Trang được đổi thành ảnh kèm lớp chữ ẩn để tìm kiếm và sao chép. Chạy hoàn toàn trên máy."
            if not ok:
                note = "Máy này chưa cài Tesseract. Bấm Nhận dạng để xem cách cài, hoặc chọn bộ máy khác."
            elif "vie" not in self.tess_langs:
                note += " Chưa có gói tiếng Việt (vie) nên chữ có dấu sẽ nhận sai."
        elif kind == "rapid":
            for key, name in self._rapid_langs:
                self.lang.addItem(name, key)
            ok = self.rapid_ok
            self.lang.setEnabled(ok)
            note = ("Model PaddleOCR chạy hoàn toàn trên máy, nội dung không gửi đi đâu. Lớp chữ ẩn được đặt lên trang gốc nên "
                    "hình giữ nguyên độ nét. Chậm hơn Tesseract (vài giây mỗi trang). Model tiếng Việt được tải về ở lần "
                    "dùng đầu tiên; chữ có nhiều dấu vẫn có thể sai, nên so thử với Tesseract trên tài liệu của bro.")
            if not ok:
                note = "RapidOCR chưa được cài trong app. Bấm nút “Cài RapidOCR…” bên dưới (cần mạng, làm một lần)."
        else:
            self.lang.addItem("Tự nhận diện (mọi ngôn ngữ)", "auto")
            self.lang.setEnabled(False)
            ok = bool(self.cfg.get("gemini_key"))
            note = ("Ảnh từng trang được GỬI LÊN Google; ở gói miễn phí Google có thể dùng nội dung để cải thiện sản phẩm, "
                    "nên đừng dùng cho hợp đồng hay tài liệu mật. Dùng chung API key với chức năng dịch, cũng bị giới hạn "
                    "lượt mỗi phút. AI đôi khi tự “đoán” chữ nhìn không rõ: nên rà lại số liệu quan trọng.")
            if not ok:
                note = ("Chưa có API key của Gemini. Mở Chuyển đổi → Dịch tài liệu, dán key vào ô API key và bấm Kiểm tra, "
                        "rồi quay lại đây.")
        if saved.get("engine") == kind:
            i = self.lang.findData(saved.get("lang"))
            if i >= 0:
                self.lang.setCurrentIndex(i)
        self.note.setText(note)
        self.b_install.setVisible(kind == "rapid" and not self.rapid_ok)
        self.b_ok.setEnabled(ok or kind == "tesseract")

    def _install(self):
        if self.install_rapid and self.install_rapid():
            self.rapid_ok = True
            i = self.engine.findData("rapid")
            self.engine.setItemText(i, self.engine.itemText(i).replace("  (chưa cài)", ""))
            self._engine_changed()

    def options(self) -> dict:
        return {"engine": self.engine.currentData(), "lang": self.lang.currentData(), "dpi": self.dpi.value(),
                "only_scans": self.only.isChecked()}

    def accept(self):
        self.cfg["ocr"] = self.options()
        super().accept()
